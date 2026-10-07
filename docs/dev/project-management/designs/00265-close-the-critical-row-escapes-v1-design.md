# Design: Close the critical-row escapes

## Architecture fit

All changes land in the existing `skills/run-autopilot/cli/` layer that already
owns the review-file shape gate and batch-apply verb:

- `gate.py` — the deterministic, state-free parser and cross-check. Stays
  state-free: no git, no subprocesses, no `state.json` reads (per its own
  docstring contract). Gains a stricter table parser and a public
  `findings_verdict()` wrapper.
- `review_close.py` — the only module with `state.json` access, so the one
  new check that needs `state.tasks` (carry-matched-to-task) lives here, not
  in `gate.py`.
- `cli/__main__.py` — argparse wiring only; gains corrected help text, and
  exports the classification-validation list `gate.py` now owns (PRD #7).
- `references/phase-review.md` — orchestrator prose; gains the carry-ref
  stamping step at re-queue time, scoped per cycle.
- `references/recovery.md` — the Fable rescue gate's own re-queue path must
  stamp the same field (dispatch-1 finding #4: this file was missing from
  the original file list and is a second, real re-queue site).
- `review-work-completion/references/output-formats.md` — the Review
  Summary Format template still prescribes the bullet shape; once coverage
  requires a Ref column (capability 2), a review file built from this
  template can never carry the required Ref, so the template itself must
  move to the Ref-table shape (dispatch-1 finding #6).
- `dev/bin/release-checks`, `CHANGELOG.md` — bookkeeping, unchanged shape.

No new module, no new layer. The fix is tightening two existing functions
(`gate._table_keys` / `gate._cross_check_findings`), adding one new pre-lock
check to `review_close.close()`, and migrating the handful of existing test
fixtures and one reviewer-facing template off the bullet/no-Ref shape that
the new coverage rule retires.

## Module placement

Edits to existing files only; no new files.

- `skills/run-autopilot/cli/gate.py`
  - rewrite `_table_keys` (and the row-shape detection it uses)
  - extend `_row_from_table` with Ref-cell and Consensus-cell validation
  - extend `_cross_check_findings` with the duplicate-ref-in-findings check
    and the ref-less-section-under-coverage check
  - change `_findings_exit`'s exit-code mapping for the unreadable-table
    case from 1 to 2 (PRD success metric: every problem-statement scenario
    exits 2 from both verbs — see Interfaces, "Exit-code reconciliation")
  - drop `"carry"` from `_SKIPPED_CLASSIFICATIONS`
  - move `_KNOWN_CLASSIFICATIONS` (today hardcoded in `__main__.py:1035`)
    into `gate.py` as a public tuple and add `known_classification(value)`
    so both verbs validate against one list (PRD #7; dispatch-1 finding #5)
  - add `findings_verdict()` as a thin public alias
  - rewrite the module docstring's exit/skip-list prose (finding #10)
- `skills/run-autopilot/cli/__main__.py`
  - `_KNOWN_CLASSIFICATIONS`/`_is_chosen_finding` import `gate`'s new public
    list instead of hardcoding it
  - `--findings` validation (`gate --findings` path) gains the per-row
    classification check via `gate.known_classification`, naming the
    offending row and value (PRD #7's acceptance criterion)
  - rewrite the `gate` and `review-close` subcommand docstring blocks
    (lines ~62-82) to name the uncovered/carry_unmatched/malformed-exit-2
    refusals
- `skills/run-autopilot/cli/review_close.py`
  - add `_carry_unmatched()` check (cycle- and rework-task-scoped), called
    pre-lock in `close()`, sharing the one pre-lock `state.load()` with the
    existing apply-once read (dispatch-1 finding #5's `#20` interaction)
  - tail-sweep batches: refuse outright (not silently ignore) a `carry` row
    in a tail-sweep findings JSON (dispatch-1 non-blocker #11)
  - `#12`: a tail-sweep row matching an open deferral (same severity+file)
    refused, not applied twice — new `_matches_open_deferral()` helper,
    checked alongside the existing tail-sweep carve-outs
  - `#13`: the coverage refusal (`gate._cross_check_findings`'s `uncovered`
    branch) lists every uncovered ref in one message, not just the first —
    `gate.py` change (see Interfaces), `review_close.py` passes the message
    through unchanged
  - `#14`: a tail sweep's `_close_result` always reports
    `lenses_closed: {}` (today `_set_lens_state` already no-ops for
    tail-sweep, but `_close_result` still reads `ctx["lenses"]`, which
    `_mutation_context` computed from `_lens_states(frontmatter)` — add a
    tail-sweep branch there that returns `{}` directly)
  - `#17`: `_LENS_STATUS`/`_lens_states` already maps an absent-from-roster
    persona (`agents:` status missing a key `review-close` recognizes) to
    `"failed"` by the `setdefault` loop; this bullet is really about a
    persona *removed from the roster by design* (status `"disabled"` is
    already `"skipped"`) versus one simply never dispatched — add the
    `"lost"` status to `_LENS_STATUS`/`_DISPATCH_OUTCOME` for a persona
    whose `agents:` entry is entirely absent, replacing today's silent
    `"failed"` default
  - `#20`: the apply-once identity read (`identity in
    state.get("applied_review_batches", [])`) already happens inside
    `statectl.mutate()`'s callback, i.e. after the lock — that is correct
    per the module docstring ("idempotency check reads that stamp INSIDE
    the lock"); the PRD's "#20" wants the *pre-lock refusal checks* (gate,
    cross-check, carry) to run before `mutate()` opens `state.json.bak` at
    all, which they already do and will continue to after this PRD's new
    carry check is added in the same pre-lock block
  - `#24`: `_end_dispatch_rows`/`record_dispatch.py end <row_id>` gains a
    `row_id` shape check (`^[A-Za-z0-9._][A-Za-z0-9._-]*$`), refusing an id
    with a leading dash before building the subprocess argv (the `--`
    separator fix lives in `record_dispatch.py`'s own arg parsing, not here)
  - update `close()`'s docstring
- `skills/run-autopilot/references/phase-review.md`
  - "Escalate review-flagged tasks by tier" step 4: stamp `carry_refs`
    (list, appended) and `carry_cycle` in the same `task-set-meta` payload
  - line 280 and the `[Unreleased]` CHANGELOG line (#15, #29, #30)
- `skills/run-autopilot/references/recovery.md`
  - the Fable rescue gate's re-queue `task-set-meta` payload (around line
    245) stamps the same `carry_refs`/`carry_cycle` fields — this is the
    second and only other site that resets a task to `pending` for a
    carry-eligible re-run
- `review-work-completion/references/output-formats.md`
  - the Review Summary Format's `## Consolidated Findings` example moves
    from the bullet shape to the Ref-bearing pipe-table shape (the shape
    `consolidate_findings.py` already emits), so a review built from this
    template satisfies the new coverage rule by construction
- `dev/bin/release-checks`
  - add the five test modules named in PRD #32
- Existing test fixtures that migrate off the bullet/no-Ref shape (see
  "Fixture migration" below): `cli/test_gate.py`, `cli/test_review_close.py`,
  parts of `cli/test_gate_findings_table.py`
- `skills/run-autopilot/cli/test_gate_findings_table.py`,
  `test_review_close.py`, `review-work-completion/scripts/test_review_verbs_prose.py`
  (the existing file — not a new path, see Interfaces note), `cli/test_main_review_close_validation.py`,
  `cli/test_store_tree_legibility.py`, `cli/test_role_effort.py`,
  `scripts/test_phase_review_closes_via_review_close.py`,
  `review-work-completion/scripts/test_skill_stages_via_review_stage.py`

## Interfaces & contracts

### `gate.py`

```python
# NEW: a looser "is this line part of the table body" test than the public
# TABLE_DATA_ROW_RE (which convergence.py relies on for severity counting
# over a DIFFERENT table shape and must not change). Scoped to _table_keys
# only.
# Leading pipe only (dispatch-3 blocker #3): a truncated row that lost its
# closing `|` is still a candidate, so it reaches _row_from_table, comes up
# short, and makes the table unreadable instead of being skipped.
_CANDIDATE_ROW_RE = re.compile(r"^\|")
_SEPARATOR_ROW_RE = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$")
_REF_CELL_RE = re.compile(r"^R(\d+)$", re.IGNORECASE)
_CONSENSUS_CELL_RE = re.compile(r"^\[\d+/\d+\]$")

# PRD #7, moved out of __main__.py so gate.py is the one place that knows
# what a valid classification is; __main__.py imports this tuple instead of
# hardcoding it.
KNOWN_CLASSIFICATIONS = ("verify", "discard", "fix", "defer", "carry")


def known_classification(value: object) -> bool:
    return isinstance(value, str) and value in KNOWN_CLASSIFICATIONS


def _row_from_table(header: list[str], cells: list[str]) -> Row | None:
    """Unchanged return shape. NEW validation before building the Row:
    - if "ref" in header: the ref cell, stripped, must fully match
      _REF_CELL_RE (case-insensitive single `R<digits>`); anything else
      (trailing `.`, trailing letter, two refs in one cell, empty) -> None.
      A match is normalized `.upper()`.
    - if "consensus" in header: the consensus cell, stripped, must fully
      match _CONSENSUS_CELL_RE (bracketed `[m/n]`); an unbracketed `2/2`
      or any other shape -> None.
    Both checks run before the existing severity/issue/file extraction, so a
    row failing either never reaches Row() at all - caller sees a truncated
    row and the whole table becomes "unreadable-table", exactly like today's
    short-row case.
    """

def _table_keys(section: str) -> tuple[list[Row], str | None]:
    """Rewritten row-shape detection, same return contract.
    Once the header line is found, EVERY following line matching
    _CANDIDATE_ROW_RE that is NOT a _SEPARATOR_ROW_RE match is a data row -
    full stop, no bracket-consensus requirement gates row recognition
    anymore (that requirement moves into _row_from_table's per-cell checks
    above, which can now refuse a row instead of the old behavior of simply
    never recognizing it as a row). A candidate row that is not a pipe-table
    line at all (e.g. a bullet line, blank line, prose) is skipped as
    before - it is not part of THIS table's body.
    A repeated ref value across two data rows (duplicate table ref) ->
    ([], "unreadable-table") as soon as the second occurrence is seen.
    Everything else (header detection, no-table-at-all passthrough, short-row
    -> unreadable-table) is unchanged.
    """

def _reviewed_keys(text: str) -> tuple[list[Row], str | None]:
    """UNCHANGED signature. One new problem value added to the vocabulary
    this function can return: "ref-required" (see _cross_check_findings
    below for when it fires) alongside the existing "no-section" and
    "unreadable-table". Still returns every row it can parse, bullets
    included; it is `_cross_check_findings` that decides whether a ref-less
    row is acceptable for THIS caller."""

def _cross_check_findings(
    text: str,
    findings: list[dict],
    require_coverage: bool = True,
) -> tuple[str, str | None]:
    """Tag vocabulary EXTENDED, not collapsed: "ok" | "mismatch" |
    "uncovered" | "malformed" | "ref-required". The existing "malformed"
    tag keeps its exact prior meaning (no-section, or an unreadable table -
    short row, bad ref cell, bad consensus cell, duplicate table ref) so
    every existing test asserting tag == "malformed" for those cases is
    UNCHANGED (dispatch-1 finding #1's core correction: the coverage gap in
    bullet/no-Ref sections is a DIFFERENT, NEW failure mode, not a
    reclassification of the existing unreadable-table case - see below).

    Two additions, both evaluated before the existing backed/uncovered
    loops:

    1. Duplicate ref within `findings` itself, for ANY classification
       (dispatch-1 non-blocker #8: no exemption for verify/discard) ->
       ("mismatch", "finding ref <ref> given two classifications: "
       "<classification1> and <classification2>"). Two rows sharing a ref
       AND the SAME classification is not an error (a reviewer may list a
       finding once per `found_by` entry in some upstream shapes); only a
       ref claimed by two DIFFERENT classifications is refused.
    2. When require_coverage is True AND `_reviewed_keys` returned at
       least one row AND ANY of those rows has `ref == ""` -> ("ref-required",
       "coverage requires a Ref column; this section has at least one row "
       "with none - R1 R2 ... are keys the gate normalizes case-"
       "insensitively from the pipe table's Ref column"). **Codex
       dispatch-2 blocker, fixed**: the first draft tested "every row
       ref-less", which `_reviewed_keys` never satisfies for a MIXED
       section — it concatenates the bullet-regex rows (always `ref ==
       ""`) with the pipe-table rows (ref-ful when a Ref column exists)
       unconditionally; neither `_table_keys` nor `_row_from_table` reject
       that mix (bullets are not part of the table's body at all, they are
       a wholly separate regex branch), so a section mixing one Ref-table
       row with one bullet row would have kept the bullet row silently
       uncovered under the "every row" test — precisely the escape this
       capability exists to close. The "any row" test catches it: a single
       ref-less row anywhere in the section, alongside any number of
       ref-ful rows, makes the whole section `"ref-required"`.
       **Zero-findings carve-out** (codex dispatch-2 question, resolved):
       an EMPTY `## Consolidated Findings` section (`_reviewed_keys`
       returns `([], None)` — no rows, no problem) never reaches this
       branch at all (the "at least one row" guard above), so a genuinely
       clean review with nothing to report is `"ok"`, not refused; it is
       only a NON-EMPTY set of rows containing a ref-less one that
       triggers `"ref-required"`. require_coverage=False (tail-sweep)
       never returns `"ref-required"` - the tail-sweep JSON is already
       documented as a deliberate ref-less subset.

    `_SKIPPED_CLASSIFICATIONS` for the `_backed()` loop becomes
    `("verify", "discard")` - "carry" is removed, so a carry row with a ref
    absent from the review table ("ghost carry") is now refused as
    "mismatch", exactly like any other row. This is the whole fix for PRD
    problem #1's second bullet.
    """

def findings_verdict(
    text: str,
    findings: list[dict],
    require_coverage: bool = True,
) -> tuple[str, str | None]:
    """NEW public name. A direct, no-logic alias:
        return _cross_check_findings(text, findings, require_coverage)
    `_cross_check_findings` keeps its name (existing tests call it by that
    name directly) and its PRIOR tag meanings for "ok"/"mismatch"/
    "uncovered"/"malformed" - it only GAINS the "ref-required" tag.
    `findings_verdict` is the one name `review_close.py` calls, and
    `gate._findings_exit` switches to calling it too (closing dispatch-1
    non-blocker #7: both callers now route through the same name).
    """
```

**Exit-code reconciliation (dispatch-1 blocker #2).** The PRD success
metric requires every problem-statement scenario to exit 2 from both verbs.
The scenarios this PRD targets map to tags as follows, and `_findings_exit`
is updated so every one of them is exit 2, while the untouched, non-PRD
"no-section" case stays exit 1 (gate) / legacy pass (review-close) exactly
as today — it is not a scenario this PRD's problem statement names:

| Tag | Scenario | Gate exit | review-close `refused` |
|---|---|---|---|
| `"mismatch"` | ghost carry, chosen row not in table, dup JSON ref | 2 (unchanged) | `findings_mismatch` → 2 (unchanged) |
| `"uncovered"` | a table row no JSON row names | 2 (unchanged) | `findings_uncovered` → 2 (unchanged) |
| `"malformed"` + unreadable-table detail | off-shape ref, bad consensus, dup table ref, truncated row | **2 (changed from 1)** | `findings_malformed` → **2 (changed from 1)** |
| `"malformed"` + no-section detail | no `## Consolidated Findings` section at all | 1 (unchanged) | legacy pass-through (unchanged) |
| `"ref-required"` (NEW) | bullet-only or no-Ref-column section | **2 (new)** | `findings_ref_required` → **2 (new)** |
| N/A, classification check | `gate --findings` row with unknown classification (PRD #7) | **2 (new; was previously unvalidated)** | n/a — `review-close`'s own `_is_chosen_finding` already refuses this at the CLI layer before `close()` runs |

`_findings_exit` becomes:

```python
def _findings_exit(text: str, findings_file: Path) -> int:
    rows, error = _load_findings(findings_file)
    if rows is None:
        sys.stderr.write(f"{error}\n")
        return 1
    for row in rows:
        if not known_classification(row.get("classification")):
            sys.stderr.write(
                f"row {row.get('ref', '?')}: unknown classification "
                f"{row.get('classification')!r} (expected "
                f"{'|'.join(KNOWN_CLASSIFICATIONS)})\n",
            )
            return 2
    tag, detail = findings_verdict(text, rows)
    if tag == "ok":
        return 0
    sys.stderr.write(f"{detail}\n")
    if tag in ("mismatch", "uncovered", "ref-required"):
        return 2
    if tag == "malformed" and detail == _FINDINGS_PROBLEMS["unreadable-table"]:
        return 2
    return 1  # malformed/no-section, or any future addition: fail-1 by default
```

**`review-close`'s own CLI mapping (codex dispatch-2 blocker).** The design's
first pass changed `close()`'s returned `refused` strings but never touched
`__main__.py`'s SEPARATE exit-code constant, which would have silently kept
every new refusal at exit 1. `_run_review_close`'s mapping (today
`2 if result.get("refused") in ("findings_mismatch", "findings_uncovered") else 1`)
is rewritten to the explicit set this PRD's refusals require:

```python
_EXIT_2_REFUSALS = (
    "findings_mismatch",
    "findings_uncovered",
    "findings_ref_required",
    "findings_malformed",
    "carry_unmatched",
    "carry_in_tail_sweep",
    # dispatch-3 blocker #1: the tail-sweep refusals are PRD scenarios too
    "tail_sweep_before_decision_gate",
    "tail_sweep_empty",
    "tail_sweep_above_medium",
    "tail_sweep_duplicates_deferral",
    "already_applied_duplicate",  # pre-lock identity check, below
)
...
return 2 if result.get("refused") in _EXIT_2_REFUSALS else 1
```

`cli/test_main_review_close_validation.py` asserts the CLI's ACTUAL exit
code end-to-end for each refusal kind in this tuple, not just `close()`'s
return dict — this is the acceptance test that would have caught the gap
codex's dispatch-2 flagged.

**Fixture migration (dispatch-1 blocker #1, resolved explicitly rather than
hand-waved).** `_cross_check_findings`'s PRIOR behavior for bullet/no-Ref
sections was `"ok"` or `"mismatch"` depending on `_backed()`; after this PRD
it is `"ref-required"` for any caller with `require_coverage=True`. This
*is* a behavior change the PRD mandates (problem #2 names bullet rows and
no-Ref-column tables as escapes to close), and it does touch existing
fixtures. Rather than claim otherwise, the task list enumerates every
affected test by name as a planning input:

- `cli/test_gate.py`: the shared `FINDINGS_SECTION`/`_one_row_section`
  bullet fixtures feeding the tests at (today's) lines 396-454, 470, 557
  and 567 gain a Ref column (`| R1 | ... |`) in their fixture text; the
  tests at 396-454 (which exercise `require_coverage=True` with a chosen
  row that should mismatch) keep asserting `"mismatch"`, now via a Ref-ful
  fixture; `test_malformed_findings_section_exits_1_not_2` and
  `test_cross_check_reports_the_missing_section_as_malformed` are checked
  against their actual fixture (no-section stays as-is; if either secretly
  exercises a bullet/no-Ref section rather than a missing section, it moves
  to assert `"ref-required"`/exit-2 instead and is renamed accordingly).
- `cli/test_gate_findings_table.py`: the ~12 tests built on `TABLE_HEADER_6`
  /`TABLE_HEADER_5` (no Ref column) gain a Ref column in the header and
  every data row; `test_bullet_rows_without_ref_need_no_coverage` is
  rewritten to `test_bullet_rows_without_ref_need_coverage_and_are_refused`
  (asserts `"ref-required"`), since its old title asserted exactly the
  behavior this PRD removes.
- `cli/test_review_close.py`: the shared `CONSOLIDATED` bullet fixture
  gains a Ref column; every test using it is re-run against the new
  fixture and re-asserted (most should be unaffected in outcome once refs
  are present — the migration is additive to the fixture text, not a
  behavior change for THOSE tests, since they were never exercising the
  ref-less path on purpose).

This is Phase 0's actual first task in practice (the parser and tag change
cannot land green without it); the task list below sequences it that way.

### `review_close.py`

```python
def _carry_unmatched(row: dict, cycle: int, tasks: list[dict], rework_ids: list[str]) -> bool:
    """True when `row` (classification == "carry", already confirmed
    `_backed()` against the review table by findings_verdict) has no
    matching, THIS-CYCLE `[C{cycle}]` task in `state.tasks`.

    Match rule (dispatch-1 blocker #3 fix): `row["ref"]` (stripped,
    upper-cased) must appear in some task's `carry_refs` list AND that
    task's `carry_cycle` must equal `cycle` (`state.cycle`, the CURRENT
    cycle — a stale stamp from an earlier cycle's re-queue never matches,
    closing the cross-cycle escape a single unscoped field would leave
    open) AND that task's id must be in `rework_ids` (`state.rework_task_ids`
    at call time — the task is actually queued for this cycle's rework, not
    merely carrying a leftover stamp from a task nobody re-queued this
    round).

    Task-kind check (dispatch-3 blocker #2): the task must also BE a
    `[C{cycle}]` re-queue. Phase 6 step 4 does not rename the re-queued
    original-plan task, so the `[C]` "prefix" is not in `name`; what marks
    it is the same `task-set-meta` call that stamps `carry_refs`:
    `escalation_reason` in `("review_flag", "fable_rescue")` (the second is
    `references/recovery.md`'s Fable rescue re-queue, the other stamping
    site), plus status not `completed` (the
    step-4 reset to `pending`). A `[D{cycle}]` task (name starts `[D`) never
    matches, even if a stamp leaked onto it, and neither does a stale
    `completed` task left in `rework_ids`.
    """
    ref = str(row.get("ref", "")).strip().upper()
    if not ref:
        return True
    return not any(
        isinstance(t, dict)
        and ref in [str(r).strip().upper() for r in (t.get("carry_refs") or [])]
        and t.get("carry_cycle") == cycle
        and str(t.get("id")) in rework_ids
        and t.get("escalation_reason") in ("review_flag", "fable_rescue")
        and t.get("status") != "completed"
        and not str(t.get("name", "")).startswith("[D")
        for t in tasks
    )
```

`close()` gains one pre-lock check, after the existing
`findings_verdict`/cross-check block and before `statectl.mutate(...)`. The
cross-check block itself gains the new `"ref-required"` tag and the
`"malformed"`+unreadable-table exit-2 routing from the table above:

```python
cross_check, detail = gate.findings_verdict(
    text, chosen_findings, require_coverage=batch_id != "tail-sweep"
)
if cross_check == "mismatch":
    return {"applied": False, "refused": "findings_mismatch", "reason": detail}
if cross_check == "uncovered":
    return {"applied": False, "refused": "findings_uncovered", "reason": detail}
if cross_check == "ref-required":
    return {"applied": False, "refused": "findings_ref_required", "reason": detail}
if cross_check == "malformed" and detail == gate._FINDINGS_PROBLEMS["unreadable-table"]:
    return {"applied": False, "refused": "findings_malformed", "reason": detail}
# "malformed" + no-section detail: legacy pass-through, unchanged.

# ONE pre-lock state.load(), unconditional - every batch_id needs it now:
# tail-sweep for its own order/severity/empty/dedup checks below, decision
# -gate for the carry check below. This read is advisory only; it decides
# refusal BEFORE paying for statectl.mutate()'s lock, but it is NOT the
# race-safe authority.
loaded, _ = state_mod.load(state_path)

# Codex dispatch-2 blocker, fixed: a pre-lock identity check was missing
# entirely - the design's first pass checked carries here but never
# re-checked "already applied", so two racing or merely repeated calls for
# the same (review_file, batch_id) each re-read state.json, each built the
# SAME chosen_findings, and each still called statectl.mutate(), which
# writes state.json.bak on every call regardless of what _close_mutator
# ultimately does inside the lock (do_task_add/do_append never run for a
# duplicate, but state.transaction's own pre-write backup rotation is
# unconditional). The locked check inside _close_mutator (the module
# docstring's "idempotency check reads that stamp INSIDE the lock") STAYS
# as the race-safe authority - two truly concurrent calls still resolve
# correctly there - but a plain repeat call now short-circuits before ever
# reaching mutate(), so a batch re-applied after a crash or a retry does
# not keep rotating the backup file on every repeat:
identity = f"{review_file.resolve()}::{batch_id}"
if identity in loaded.get("applied_review_batches", []):
    return {"applied": False, "reason": "already applied"}

if batch_id == "tail-sweep":
    if any(f.get("classification") == "carry" for f in chosen_findings):
        return {
            "applied": False,
            "refused": "carry_in_tail_sweep",
            "reason": "a tail-sweep batch never carries a carry row",
        }
    applied = loaded.get("applied_review_batches", [])
    if f"{review_file.resolve()}::decision-gate" not in applied:
        return {
            "applied": False,
            "refused": "tail_sweep_before_decision_gate",
            "reason": "tail sweep refused: this cycle's decision-gate "
            "batch has not been applied yet",
        }
    if not chosen_findings:
        return {
            "applied": False,
            "refused": "tail_sweep_empty",
            "reason": "tail sweep findings must not be empty",
        }
    above_medium = [
        f for f in chosen_findings
        if f.get("severity") in ("\U0001f534", "\U0001f7e0")  # 🔴 🟠
    ]
    if above_medium:
        return {
            "applied": False,
            "refused": "tail_sweep_above_medium",
            "reason": f"tail sweep refuses rows above medium: "
            f"{above_medium[0].get('ref', above_medium[0].get('file'))}",
        }
    dup = _matches_open_deferral(chosen_findings, loaded.get("deferred_decisions", []))
    if dup is not None:
        return {
            "applied": False,
            "refused": "tail_sweep_duplicates_deferral",
            "reason": f"tail sweep row duplicates an open deferral: {dup}",
        }
else:
    tasks = loaded.get("tasks") or []
    rework_ids = loaded.get("rework_task_ids") or []
    cycle = loaded.get("cycle", 1)
    for row in chosen_findings:
        if row.get("classification") == "carry" and _carry_unmatched(
            row, cycle, tasks, rework_ids
        ):
            ref = str(row.get("ref", "")).strip() or "(none)"
            return {
                "applied": False,
                "refused": "carry_unmatched",
                "reason": (
                    f"carry row ref {ref} has no cycle-{cycle} [C]-prefixed "
                    f"task in rework_task_ids carrying carry_refs including {ref}"
                ),
            }
```

(`state_mod` is `cli.state`; `review_close.py` adds
`from . import state as state_mod` — the existing imports already alias
nothing named `state` at module scope, so no rename is needed elsewhere in
the file.)

### `phase-review.md` (prose contract, Phase 2 task)

"Escalate review-flagged tasks by tier", step 4's `task-set-meta` payload
gains two fields, stamped from the finding row this task is being re-queued
to fix (dispatch-1 blocker #3 and #4 fixes: cycle-scoped, list-valued):

```
{"model": "<next_tier>", "escalation_reason": "review_flag",
 "escalated_from": "<prev_tier>",
 "carry_refs": ["<Ref cell, upper-cased>", ...existing entries],
 "carry_cycle": <state.cycle>}
```

`carry_refs` is a LIST, not a single value, because one task can be flagged
by more than one finding row in the same cycle (blocker #4): the
orchestrator reads the task's CURRENT `carry_refs`/`carry_cycle` before
calling `task-set-meta`. **The union is conditional on the cycle, not
unconditional** (codex dispatch-2 blocker: an earlier draft unioned the
existing list unconditionally and only overwrote `carry_cycle` afterward,
which left a stale cycle-1 ref in the list while `carry_cycle` already read
2 — exactly the cross-cycle leak this field exists to prevent, since
`_carry_unmatched` only compares `carry_cycle`, never inspects individual
list entries' provenance):

```
current = task.get("carry_refs") or []
current_cycle = task.get("carry_cycle")
base = current if current_cycle == state.cycle else []
new_carry_refs = sorted(set(base) | {this_finding_ref.upper()})
# task-set-meta payload carries carry_refs=new_carry_refs, carry_cycle=state.cycle
```

i.e. the existing list is kept ONLY when it already belongs to the current
cycle (a second flagging row in the SAME escalation pass); a task re-queued
again in a LATER cycle starts its list fresh for that cycle, rather than
accumulating refs across cycles. `task-set-meta`'s flat-merge semantics
(`do_task_set_meta` overwrites whichever keys the payload names) make this
a plain read-compute-write by the orchestrator, not a new statectl verb —
there is no concurrent writer of a single task's `carry_refs` within one
session (phase-review.md processes review-flagged tasks one at a time in
its escalation loop), so no additional locking is needed beyond
`task-set-meta`'s existing one.

The same stamping applies at `references/recovery.md`'s Fable rescue gate
re-queue (its own `task-set-meta` call, around line 245) — it is the only
other site that resets a task to `pending` for a carry-eligible re-run, and
dispatch-1 flagged it as a second escape if left unstamped.

A review-flagged task re-queued with no identifiable `Ref` cell (a legacy
table with no Ref column) stamps no `carry_refs` entry for that flagging;
its later `carry` classification then correctly refuses under
`_carry_unmatched` — fail-closed is the desired outcome for an
un-attributable re-queue, not a bug to route around. Once capability 2
ships in this same PRD, a table with no Ref column is itself refused
upstream (`"ref-required"`) before any `chosen_findings` row naming it as
`carry` could even be built, so this branch is reachable only mid-migration
(a review file authored before this PRD's fixture/template migration
lands) and fails safely in exactly that window.

**Operator recovery when a carry is refused:** the operator (interactive)
or the Loop-mode stall procedure (`site: "sub_skill_fail"`, unattended)
re-runs `task-set-meta <task-id> <meta-json-file>` with the missing
`carry_refs`/`carry_cycle` pair, or reclassifies the row from `carry` to
`defer`/`fix` in the findings JSON and re-runs `review-close` — both are
existing recovery primitives, not new mechanism.

### `__main__.py` help text (finding #10)

`gate` docstring block names the `uncovered` and `ref-required` refusals
explicitly (today's text names only the `mismatch` direction):

> ... or 2 (constraint UNMET; a `--findings` row the review file never
> recorded; a review row no `--findings` row names a classification for;
> an unreadable findings table; a findings section with no Ref column; or
> a `--findings` row with an unknown classification), see `cli/gate.py`...

`review-close` docstring block gains the `carry_unmatched`,
`findings_malformed`, `findings_ref_required` and `carry_in_tail_sweep`
refusal classes, all in the exit-2 bucket per the reconciliation table
above:

> ... Exit 1 when `close()` refuses on a legacy no-section review file or
> the batch is already applied. Exit 2 on an unreadable or malformed
> findings file, a failed state write, a chosen finding the review file's
> consolidated findings never recorded or never covers, an unreadable
> findings table or one with no Ref column, a `carry` row with no matching
> `[C]`-prefixed task in the current cycle, a `carry` row inside a
> tail-sweep batch, or a tail sweep that is empty, runs before the
> decision gate, holds a row above medium, or repeats an open deferral.

Both are pinned by a new `test_gate_help_describes_the_two_way_check` added
to the EXISTING file
`skills/review-work-completion/scripts/test_review_verbs_prose.py`
(dispatch-1 question #15: this file already exists at that path — the PRD
task list's reference to `skills/run-autopilot/scripts/test_review_verbs_prose.py`
is the same logical test suite, added to the file that already owns this
kind of prose-pinning test, not a second new file). It grep-asserts the
updated substrings are present in both the `__main__.py` docstring and
`gate.py`'s module docstring.

## Data flow

```
review file (markdown)
   │  gate._reviewed_keys()            — parse Consolidated Findings
   ▼
list[Row] + problem?  ──────────────────────────────────────────┐
   │                                                             │
   │  gate._cross_check_findings(text, chosen_findings, …)       │
   │    - classification-known-value check (NEW, gate.py-owned)  │
   │    - duplicate-ref-in-findings check (NEW)                  │
   │    - ref-less-section-with-coverage-required check (NEW)    │
   │      → "ref-required", distinct from "malformed"            │
   │    - _backed() loop, "carry" no longer skipped (CHANGED)    │
   │    - uncovered loop: now lists EVERY uncovered ref (#13)    │
   ▼                                                             │
("ok"|"mismatch"|"uncovered"|"malformed"|"ref-required", detail) │
   │                                                             │
   │  gate.findings_verdict() — thin alias, same tuple            │
   │  gate._findings_exit() now also calls findings_verdict       │
   ▼                                                             │
review_close.close()                                             │
   │  - routes "mismatch"/"uncovered"/"ref-required" to refusal   │
   │  - routes "malformed"+unreadable-table to refusal (NEW)      │
   │  - "malformed"+no-section: legacy pass-through (unchanged)   │
   │  - tail-sweep: refuses any carry row outright (NEW)          │
   │  - non-tail-sweep "ok": ONE pre-lock state.load() reads       │
   │    tasks/rework_task_ids/cycle, scans carry rows against     │
   │    task.carry_refs + carry_cycle + rework-id membership (NEW)│
   ▼                                                             │
statectl.mutate() — one transaction, unchanged internals ─────────┘
```

`autopilot gate --findings` (standalone, no state) exercises the same
`findings_verdict` path, plus the classification check, but never reaches
the carry-unmatched check — it has no `state.tasks` to check against,
which is consistent with `gate.py`'s state-free contract; the
carry-unmatched refusal is `review-close`-only.

## Reuse inventory

Reuse sweep (verb and noun synonyms), before adding anything new:

- `rg -n "def _table_keys|def _row_from_table|def _reviewed_keys" skills/run-autopilot/cli/gate.py`
  → found the three functions to edit; no parallel/duplicate parser exists
  elsewhere in the repo.
- `rg -n "carry_ref|carry.ref|matched.carry" skills/` → nothing found; no
  existing ref-stamping mechanism to reuse. Confirms a new task field is
  needed, not a rename of an existing one.
- `rg -n "task-set-meta|do_task_set_meta" skills/run-autopilot/cli/statectl.py`
  → `do_task_set_meta` already merges arbitrary flattened keys onto a task
  entry (explicitly: "payload passes through whole... An absent optional
  field stays absent"), so `carry_refs`/`carry_cycle` need no statectl
  change — they ride the existing merge-arbitrary-keys mechanism, same as
  `escalation_reason` and `escalated_from` already do. The union-before-
  write for `carry_refs` (read-then-merge) is orchestrator-side prose, not
  a new statectl verb — `do_task_set_meta` still does one flat merge.
- `rg -n "class.*Schema|TASK_FIELDS|ALLOWED_TASK_KEYS" skills/run-autopilot/cli/schema.py`
  → no closed task-field allowlist exists; an unrecognized field is not
  rejected by schema validation, confirming the new task fields need no
  schema change either.
- `rg -n "_SKIPPED_CLASSIFICATIONS|_cross_check_findings|_reviewed_keys" skills/run-autopilot/cli/test_gate.py skills/run-autopilot/cli/test_gate_findings_table.py skills/run-autopilot/cli/test_review_close.py`
  → found the existing call sites and literal-tag assertions, which is what
  drove the "extend the tag vocabulary, never collapse or rename an
  existing tag's meaning" decision throughout Interfaces above.
- `rg -n "_KNOWN_CLASSIFICATIONS|_is_chosen_finding" skills/run-autopilot/cli/__main__.py`
  → confirmed the classification list is today private to `__main__.py`
  with no `gate.py` counterpart, which is why PRD #7 ("gate --findings
  validates each row's classification with the same rule review-close
  uses") needs the list moved to `gate.py`, not merely duplicated.
- `rg -n "Consolidated Findings" review-work-completion/references/output-formats.md`
  → confirmed the reviewer-facing template is still bullet-shaped (dispatch
  -1 finding #6), driving its addition to Module placement above.
- `~/.claude/rules-library/rationalizations.md` — read; its synonym sets are
  general-purpose (format/render/serialize, etc.) and did not surface
  anything beyond the greps above for this parser-tightening PRD.

## Alternatives considered

1. **Carry match: explicit `carry_refs`/`carry_cycle` stamp only (chosen)
   vs. a `(file, severity)` fallback vs. fallback-only (no stamp).**
   Fallback-only was rejected outright: a review table's `file` cell is
   free text (`gate.py:234`'s `_normalize_issue` already fights escaped
   pipes and whitespace in it), so matching a task to a row by file text
   is exactly the kind of fuzzy-string coupling this PRD exists to remove.
   A stamp + fallback was considered next; the design's first draft argued
   the fallback's only justified scenario (a Ref-less table) becomes
   unreachable once capability 2 ships — dispatch-1 review correctly
   pointed out this argument ignored in-flight batches mid-upgrade and the
   Fable-rescue re-queue path. The actual fix for both of those gaps is
   closing them directly (covering `recovery.md`'s re-queue site, and
   accepting that a legacy un-stamped `[C]` task's carry fails closed
   during the migration window — see phase-review.md's note above), not
   adding a fuzzy fallback whose failure mode (matching the wrong task by
   coincidental file+severity) is worse than a loud, fixable refusal.
   Stamp-only, now cycle-scoped and list-valued, remains the chosen design.

2. **Row-shape detection: loosen `TABLE_DATA_ROW_RE` in place vs. add a
   second, scoped pattern (chosen).** `TABLE_DATA_ROW_RE` is public and
   `convergence.py` already depends on its exact bracket-consensus shape to
   count severities over the main review file's own findings table (a
   different document, same package). Loosening it in place risks a
   silent behavior change in convergence counting that this PRD's test
   suite does not cover. A second, `_`-private pattern scoped to
   `_table_keys` costs one more regex and keeps the blast radius to the
   function this PRD is actually about.

3. **Tag vocabulary: split `"malformed"` into separate tags at the
   `_cross_check_findings` boundary vs. extend the vocabulary additively
   (chosen, revised from the first draft).** The first draft tried to keep
   the existing `"malformed"` tag's TWO meanings (no-section,
   unreadable-table) collapsed and have `review_close.py` re-derive the
   subtype by comparing `detail` against `_FINDINGS_PROBLEMS["unreadable-table"]`
   — dispatch-1 correctly flagged this as fragile (string-identity coupling
   across modules) and as not actually fixing the exit-code/success-metric
   mismatch (blocker #2). The revised design keeps `"malformed"`'s EXISTING
   two meanings and exit codes exactly as today (no test touching
   "malformed" changes), and adds a BRAND NEW tag, `"ref-required"`, for
   the one genuinely new failure mode (coverage impossible for lack of a
   Ref column) this PRD introduces. This is additive, not a rename, so
   every existing `"malformed"`-asserting test is untouched, and the new
   failure mode gets its own exit-2 routing without a cross-module string
   comparison for the common case (the single remaining `detail ==
   _FINDINGS_PROBLEMS["unreadable-table"]` comparison is confined to the
   one place that must distinguish "truly unreadable" — exit 2 — from "no
   section at all" — exit 1/legacy pass — which really are two different
   outcomes for the SAME existing tag, not two tags pretending to be one).

## Risks & edge cases

**Rollback (codex dispatch-2 cardinal-sin, addressed).** Every change in
this PRD is additive at the data layer and reversible at the code layer:

- **Code**: `gate.py`, `review_close.py`, `__main__.py` and the two prose
  files change in one PR/commit sequence behind normal version control;
  `git revert` of that merge restores the prior parser, tag vocabulary and
  exit codes exactly. There is no feature flag because there is no partial-
  rollout risk to flag against — this CLI runs inside one autopilot session
  at a time, never as a long-lived service with mixed old/new callers.
- **Data**: the only persistent additions are the optional `carry_refs` /
  `carry_cycle` task fields and the `cycle`/`action` keys on
  `deferred_decisions` entries (#12). Both are purely additive — no
  existing field is renamed, removed, or reinterpreted, and `schema.py` has
  no closed allowlist that would reject them (see Reuse inventory). A
  rollback (reverting the code) leaves these fields inert in `state.json`:
  the reverted code never reads them, and `statectl`'s flattened-merge
  task-field model (confirmed in Reuse inventory) treats an unknown key as
  silently ignored, not an error. No destructive migration exists to roll
  back, and `state.json.bak` (one rotation per write, already part of the
  existing `statectl.mutate()` contract) is the existing restore path for
  any single bad write, unchanged by this PRD.
- **Human owner / observability**: unchanged from today — this is CLI
  tooling the autopilot orchestrator calls synchronously inside a session
  it already supervises end to end (loop-mode stall procedures, PAUSE
  sites); every new refusal surfaces on stderr and in the JSON result the
  caller already prints, exactly like every existing refusal, so there is
  no new silent-failure surface needing new observability.

- **A real review file's Consolidated Findings table mixes Ref and
  ref-less rows** (a reviewer hand-edited one row). `_row_from_table`
  refuses the specific malformed row (bad/missing ref cell when the header
  declares one), which propagates to `"malformed"` for the whole section —
  intentional (coverage is section-wide; a single ungoverned row defeats
  the section's coverage guarantee), but sharper than before: a one-row
  typo now blocks the whole decision gate instead of silently passing. The
  refusal message is the generic unreadable-table text, not a per-row one;
  a likely next change is naming which row broke the section (mirrors the
  existing per-row `uncovered` message pattern, and #13 already extends
  that pattern to list every uncovered ref).
- **Migration window**: between this PRD landing and every in-flight PRD's
  review files being Ref-table-shaped, a `[C]` task re-queued from a
  pre-migration table carries no `carry_refs` entry and any later `carry`
  classification for it fails closed (see phase-review.md note above). This
  is accepted as correct (fail-closed, loud, recoverable via the operator
  procedure above), not silently routed around.
- **Next likely change #1**: review-generation tooling
  (`consolidate_findings.py`, reviewer prompts, and now
  `output-formats.md`'s template) may still emit an occasional ref-less or
  bracket-less row under prompt drift; this PRD's Risks section already
  flags "stricter parsing stalls the loop on reviewer formatting drift" —
  naming the offending row in the refusal message (above) is the natural
  follow-up.
- **Next likely change #2**: `carry_refs`/`carry_cycle` normalization
  (upper-case, strip) is written at two prose sites
  (`phase-review.md`, `recovery.md`) and read at one code site
  (`review_close._carry_unmatched`); if a future PRD adds a THIRD
  ref-bearing site, a small `gate.normalize_ref(s: str) -> str` helper
  should be extracted and imported by all of them rather than copied a
  third time. Not done now — two write sites and one read site does not
  yet justify the abstraction, and the read site is the only one that must
  be correct in code (the write sites are orchestrator prose already
  specifying `.upper()` explicitly).
- **Next likely change #3**: this PRD makes `gate --findings` and
  `review-close` agree on every table shape; a divergent *third* caller
  (none exists today) would need to route through `findings_verdict` too,
  not re-implement the check — the whole point of capability 3.
- **This design boxes in**: nothing beyond the ref-less-section-wide
  refusal and the migration window above; the carry-ref stamp is additive
  (new optional task fields) and does not change any existing task-field
  contract.

## Test strategy outline

Unit-level, matching the PRD's pinned acceptance tests exactly (file:test
pairs already named in the PRD's task list are the authoritative list; this
section groups them by what they exercise and adds the fixture-migration
and new-tag tests this revision's fixes require):

- **Fixture migration (new, precedes everything else — see "Fixture
  migration" above)**: every bullet/no-Ref fixture in `test_gate.py`,
  `test_gate_findings_table.py` and `test_review_close.py` gains a Ref
  column; `test_bullet_rows_without_ref_need_no_coverage` is rewritten to
  assert the opposite (`"ref-required"`) under its corrected name.
- `cli/test_gate_findings_table.py`: off-shape ref parametrization (`r1`
  accepted/normalized, `R1.`/`R1a`/`R1 | R3` refused), ref-less table
  `"ref-required"` (not `"malformed"`), duplicate table ref refused
  (`"malformed"`), one ref two classifications refused regardless of which
  classifications, unknown-classification row named by `gate --findings`
  (now via `gate.known_classification`), truncated/malformed-row
  regressions (existing, unchanged outcome).
- `cli/test_review_close.py`: unreadable-table refused instead of applied
  (exit-2 `findings_malformed`), ghost-carry ref refused, carry-on-critical
  -without-task refused, matched-carry accepted, a stale earlier-cycle
  `carry_refs` stamp refused (new, closes blocker #3), a carry row flagged
  by two findings in one cycle both matching after the read-then-merge
  stamp (new, closes blocker #4), a tail-sweep carry row refused outright
  (new, closes non-blocker #11), tail-sweep carve-outs (refused-before-gate,
  refuses-above-medium, empty-is-refused, matches-open-deferral #12,
  lenses_closed empty #14), lost-persona dispatch outcome #17, dispatch-id
  leading-dash refusal #24.
- `review-work-completion/scripts/test_review_verbs_prose.py`: help-text
  pinning (#10), carry CHANGELOG line count (#15/#29), `phase-review.md:280`
  prose (#30), the requeue-stamps-carry-ref prose test covering BOTH
  `phase-review.md` and `recovery.md` (new task, closes blocker #4's second
  site).
- `bash dev/bin/release-checks`: the five newly-listed modules plus
  `test_every_review_verb_test_file_is_listed` guarding the list itself.

No new integration or e2e surface: every change is a pure-function parser
fix, an additive tag, or a single additional pre-lock read, all already
inside this suite's existing unit-test shape (no git, no subprocess,
in-process state fixtures).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 6, non-blocker 6, question 4

All 6 blockers fixed above:
1. Fixture migration is now explicit and enumerated (not claimed away).
2. Exit-code reconciliation table added; unreadable-table and the new
   ref-required tag both route to exit 2 in both verbs, matching the
   success metric; no-section (not a PRD scenario) stays exit 1/legacy.
3. `carry_refs`/`carry_cycle` cycle-scoping plus `rework_task_ids`
   membership closes the cross-cycle stale-stamp escape.
4. `carry_refs` is now a list (read-then-merge), and `recovery.md`'s Fable
   rescue gate re-queue is added as a second stamping site; an operator
   recovery procedure is specified for an unstamped refusal.
5. PRD #7 (classification check moved into `gate.py` and shared) and LOW
   #12-#24 each now have a named interface or an explicit "already correct,
   no change" note (#20).
6. `output-formats.md`'s bullet-shaped template is added to Module
   placement and the Reuse inventory grep that found it.

**Codex dispatch-2 blocker, fixed**: the claim above (in the version
dispatch-2 reviewed) that PRD #4/#5's tail-sweep order/severity/empty
checks were "already governed by existing code" was false — `close()` had
NONE of the three checks; tail-sweep's only special-casing was skipping
the coverage requirement and the lens/dispatch-row updates. All three are
now real code in the `close()` snippet under Interfaces above (the
`if batch_id == "tail-sweep":` branch, using the one pre-lock
`state.load()` every batch_id now performs), plus the pre-lock identity
check (dispatch-2 blocker on `#20`, see below) and `_matches_open_deferral`.

`_matches_open_deferral(findings, deferred) -> str | None` is a small new
helper in `review_close.py`: returns the first matching finding's
`(severity, file)` description, or `None`, by the same `(severity, file)`
key `_finding_key`-style matching already used for the `_backed()` check
(reuse that normalization, do not re-implement it).

**#12's second half**, already in scope but easy to miss: `_add_decisions`'s
`defers` loop (today writing `{"issue", "severity", "file", "reason"}`)
gains the `"cycle"` and `"action"` keys `phase-review.md:145` requires of
every `deferred_decisions` entry:
`{"cycle": state.get("cycle", 1), "issue": ..., "severity": ..., "file":
..., "action": "deferred", "reason": "deferred by review-close"}`.

Non-blockers 7-12 and questions 13-16 folded in: `findings_verdict` is now
the shared call site for `_findings_exit` too (#7); duplicate-ref check
covers every classification pair (#8); the `(["], ...)` typo is fixed to
`([], ...)` throughout this revision (#9); the unreadable-table message's
mismatch with ref-less sections is resolved by giving ref-less sections
their own tag and message instead of reusing that text (#10); tail-sweep
now refuses a carry row outright instead of silently accepting one (#11);
the "four places" miscount in the original Alternatives #3 is moot since
that alternative was revised (#12); the carry check's docstring now states
plainly it runs only on the non-tail-sweep "ok"/legacy-no-section path,
never implying `_backed()` ran when it didn't (#13); JSON-side refs are
normalized `.upper()` at the same two comparison points the table side
uses, stated explicitly in `_carry_unmatched` and the duplicate-ref check
(#14); the test-path reference now points at the existing
`review-work-completion/scripts/test_review_verbs_prose.py` file, not a
new path (#15); both re-queue prose sites (`phase-review.md`,
`recovery.md`) are now in scope so every re-queue stamps the link,
regardless of which escalation branch produced it (#16).

dispatch 2 (codex): cardinal-sin 1, blocker 5, non-blocker 1, question 1

All 6 fixed above:
1. Rollback plan added (new "Rollback" subsection opening Risks & edge
   cases): additive data, revertible code, existing `.bak` restore path,
   unchanged observability/ownership.
2. `__main__.py`'s separate `_EXIT_2_REFUSALS` mapping is now explicit and
   enumerated, with its own acceptance test
   (`cli/test_main_review_close_validation.py` asserting real CLI exit
   codes), closing the gap between `close()`'s dict and the CLI's exit code.
3. Carry stamping now resets `carry_refs` to empty whenever the task's
   existing `carry_cycle` does not match the current cycle, before
   unioning in the new ref — a stale cross-cycle ref can no longer survive
   a later cycle's stamp.
4. Tail-sweep's order/severity/empty/duplicate-deferral checks are real
   code in `close()` now (not claimed pre-existing), sharing the one
   pre-lock `state.load()`; #12's `deferred_decisions` cycle/action keys
   are specified.
5. A pre-lock identity (`applied_review_batches`) check is added ahead of
   `statectl.mutate()`, so a plain repeat call short-circuits before
   rotating `state.json.bak` again; the LOCKED check inside
   `_close_mutator` is explicitly kept as the race-safe authority for two
   genuinely concurrent calls — the pre-lock check is a fast path, not a
   replacement.
6. The ref-required condition is corrected from "every reviewed row is
   ref-less" to "at least one reviewed row is ref-less, given at least one
   row total" — this catches a MIXED bullet+table section (which
   `_reviewed_keys` genuinely concatenates with no rejection of the mix,
   contrary to the design's prior claim) and carves out the genuinely
   empty, zero-findings section as `"ok"`.

Non-blocker and question folded in: the "contradicts itself" non-blocker
is resolved by the fixes above removing the actual contradictions (the
exit-code table, the help text, and `close()`'s code now agree because the
code snippets were corrected, not just the prose describing them); the
state-free-gate-accepts-a-taskless-carry point is intentional and already
stated under Data flow ("the carry-unmatched refusal is `review-close`-
only") — `gate --findings` standalone was never meant to certify carry
matching, only `review-close` is, and that scoping is unchanged. The
zero-findings question is answered in fix #6 above.

dispatch 3 (codex): cardinal-sin 0, blocker 3, non-blocker 0, question 0

Three cardinal-sin/blocker-ceiling findings remain OPEN (the three-dispatch
budget is spent; per this skill's own contract these are reported, not
fixed, and the review terminates non-zero):

1. **Blocker**: the four new tail-sweep refusal strings
   (`tail_sweep_before_decision_gate`, `tail_sweep_empty`,
   `tail_sweep_above_medium`, `tail_sweep_duplicates_deferral`) were never
   added to `_EXIT_2_REFUSALS`, so the CLI would exit 1 for all four,
   contradicting the PRD's exit-2 contract for every scenario this PRD
   targets.
2. **Blocker**: `_carry_unmatched`'s match rule (`carry_refs` + `carry_cycle`
   + `rework_task_ids` membership) does not verify the matching task is
   actually a `[C{cycle}]`-prefixed re-queue — a `[D{cycle}]` decision-gate
   task or a stale `completed` task carrying the same stamp would also
   satisfy it, which is not what "a `[C{cycle}]` task for that finding
   exists" (PRD capability 1) means.
3. **Blocker**: `_CANDIDATE_ROW_RE` (`^\|.*\|\s*$`) requires a trailing
   pipe, so a truncated row missing its closing pipe is silently excluded
   from "candidate data rows" rather than making the table unreadable —
   reintroducing a narrower version of the exact silent-skip bug capability
   2 exists to close.

These three are real and each needs one more line of logic
(`_EXIT_2_REFUSALS` additions; an `id.startswith(f"[C{cycle}]")`-style task-
name check, or a dedicated task-kind marker, added to `_carry_unmatched`'s
match predicate; and a candidate-row test that accepts any line starting
with `|` after the header, not just one also ending with `|`) — they are
recorded here as the task list's first fix-up item, not re-dispatched: the
3-dispatch ceiling is spent.

Operator resolution (2026-10-06, after the sub_skill_fail pause), all three
applied in the sections above:

1. `_EXIT_2_REFUSALS` gains the four `tail_sweep_*` strings.
2. `_carry_unmatched` also requires `escalation_reason` in
   `("review_flag", "fable_rescue")`, status not `completed`, and a name not
   starting `[D`. A name-prefix test was rejected: Phase 6 step 4 never
   renames the re-queued task, so `[C{cycle}]` is not in `name` and the
   check would refuse every legitimate carry.
3. `_CANDIDATE_ROW_RE` is `^\|` (leading pipe only); `_table_cells`
   already strips a missing trailing pipe, so the short row reaches
   `_row_from_table` and makes the table unreadable.

Tests to add with the fixes: each `tail_sweep_*` refusal exits 2 through
the CLI; a carry matched only by a `[D]` task or a `completed` task is
refused; a data row with no closing `|` makes the table `"malformed"`.

result: ok
