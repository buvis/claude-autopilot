## Architecture fit

Two existing layers already own the two capabilities this PRD narrows, so
nothing new is introduced:

- **`skills/run-autopilot/cli/verification.py`** — the single coded reuse rule
  (`reuse_verdict`, `_record_shape_ok`, `normalize_command`, `_write_record`).
  This PRD narrows `normalize_command` only; `_write_record` already stores
  whatever `normalize_command` returns, so it ends up storing the raw
  (whitespace-collapsed) command with no code change of its own.
- **`skills/review-work-completion/SKILL.md` step 6** (`## Compose the
  "Tests:" line`) — today carries its own, weaker, prose reuse test (`sha`
  equals HEAD and counts non-null) that duplicates and disagrees with
  `review-stage`'s `reuse_verdict` call in step 3. This PRD deletes that
  prose rule; step 6 becomes a pure consumer of step 3's output. Two other
  spots in the same file describe the record-reading model this removes and
  must change with it: line 181 ("step 6 ... reuses that record instead of
  running the suite again") and line 324 ("test counts do not exist until
  step 6") — both are now false once step 3 is the sole owner of the
  counts, and are in scope for this PRD's edit, not just the step-6
  paragraph.

No new module, no new file beyond the two test files and the prose edits the
PRD's Repository Structure section already names.

## Module placement

Edits only, no new production files:

- `skills/run-autopilot/cli/verification.py` — edit `normalize_command` only
  (narrow it); `_write_record` is unaffected in code, its stored value just
  changes shape because of what `normalize_command` now returns.
- `skills/run-autopilot/cli/test_verification_dirty.py` — edit one existing
  test's expectation, add two new tests.
- `skills/review-work-completion/SKILL.md` — edit step 6's prose (delete the
  sha/counts rule, state the single source), plus lines 181 and 324 (the two
  other spots describing the record-reading model this PRD removes).
- `skills/review-work-completion/scripts/test_tests_line_source_prose.py` —
  new prose-pin test file.
- `skills/work/references/final-verification.md` — edit one sentence about
  what the record stores.
- `CHANGELOG.md` — correct line 44, add an `[Unreleased] ### Changed` line.
- `dev/bin/release-checks` — register the new prose test file.

## Interfaces & contracts

### `verification.normalize_command(command: object) -> str`

```python
def normalize_command(command: object) -> str:
    """Collapses whitespace only. A non-str maps to ""."""
    if not isinstance(command, str):
        return ""
    return " ".join(command.split())
```

Removes the two `for shell in ("bash ", "sh "):` / `removeprefix("./")` lines
entirely. No new parameters, no new return shape — same signature, same
callers (`_record_shape_ok`, `reuse_verdict`, `_write_record`), all of which
already call it positionally with one string argument, so no call site
changes.

### `verification._write_record(cwd, command, sha, cycle, result) -> None`

**Not edited.** Signature and body are unchanged — `_write_record` already
calls `normalize_command(command)` before storing it (line 385); narrowing
`normalize_command` is the entire fix. `_write_record`'s stored value becomes
"whitespace-collapsed, as run" automatically, with no code change of its own.
Listed here only because the PRD's own Module section names it as an
export; the contract is: **the `command` field in the written record equals
`normalize_command(command)`, and that function now does whitespace collapse
only.**

### `skills/review-work-completion/SKILL.md` step 6 (prose contract)

**Where step 6 reads `gate.tests_line` from.** `review-stage` (step 3,
`cli/review_stage.py` `_append_context_blocks` line 766) computes
`summary["gate"]["tests_line"]` and appends it verbatim as the staged
context file's own section (line 774): `_append(context, f"## Test gate\n\n
{summary['gate']['tests_line']}")`. Step 6 reads **that `## Test gate`
section of the staged context file it already has in hand** (the same file
step 4's reviewers read) — not a separate JSON field, not
`last-verification.json` directly. "Absent" means that section does not
exist in the context file at all, which happens only on a **standalone
(non-autopilot) run that never invoked `review-stage`** — `--gate-command`
is `required=True` on the `review-stage` CLI (`cli/__main__.py:1018`), so
under autopilot the section always exists once step 3 has run; it cannot be
blank or omitted by review-stage itself.

`_tests_line`/`run_gate_line` produce one of a **closed set of shapes**.
`cli/gate.py`'s `TESTS_RE` (`^Tests: (\d+ passed.*|none \(docs-only\))\s*$`)
is the gate `check_review_file.py` applies to whatever ships in the review
file — only some of these shapes match it:

| `gate.tests_line` shape | produced when | matches `TESTS_RE`? | step 6 action |
|---|---|---|---|
| `Tests: N passed, M failed, K skipped (reused from last-verification.json at <sha>)` | `reuse_verdict` returned `"reused"` | yes | copy verbatim |
| `Tests: N passed, M failed, K skipped (suite run this cycle)` | a fresh `run_gate` call parsed counts | yes | copy verbatim |
| `Tests: 0 passed, 0 failed, 0 skipped (suite timed out after <n>s, treated as failed)` | the gate run timed out | yes (it is a counts line) | copy verbatim |
| `Tests: counts unavailable (suite run this cycle, exit <n>, no PASS/FAIL/SKIP/EXIT summary line)` | the run produced no parseable summary | **no** | fall back (see below) |
| `Tests: (gate skipped: working tree dirty outside the store)` | `result["dirty"]` was true | **no** | fall back (see below) |
| `Tests: (gate failed to run: <err>)` | `review_stage.py:770`, the gate process itself failed to launch | **no** | fall back (see below) |
| *(section absent entirely)* | standalone run, `review-stage` never invoked | n/a | fall back (see below) |

**Fallback rule.** Step 6 runs `autopilot verify --gate-command "<full suite
command>" --cycle <state.cycle>` once in the FOREGROUND, and composes the
`Tests:` line from that result, whenever the `## Test gate` section is
**absent, or present but its line does not match `TESTS_RE`** (the three
non-counts shapes above). Step 6 copies `gate.tests_line` **verbatim,
unmodified** only in the three `TESTS_RE`-matching rows; it never copies a
line that would fail the gate. This keeps the PRD's narrow scope (collapse
the duplicated reuse decision) without introducing a new way for step 8 to
write an ungateable review file — a regression the original "copy every
shape verbatim" draft of this design would have caused.

Replace the paragraph starting `**Compose the \`Tests:\` line.**` (SKILL.md
line 402) so that, after the existing docs-only check (unchanged, stays
first), the non-docs-only branch reads:

> Otherwise, read the `## Test gate` section of the staged context file.
> When its line is a counts line (matches `cli/gate.py`'s `TESTS_RE` — the
> `reused`, `suite run this cycle`, or `timed out` forms), take the `Tests:`
> line verbatim from it: `review-stage`'s `reuse_verdict` call (step 3) is
> the only reuse decision, and its suffix is already baked into the line
> step 6 copies — never re-derive reuse from `sha`/counts here. Otherwise
> (the section is absent, or holds a `counts unavailable`/`dirty`/`failed to
> run` line that is not itself a counts line) run `autopilot verify
> --gate-command "<full suite command>" --cycle <state.cycle>` once in the
> FOREGROUND and compose the line from that result, suffixed
> `(suite run this cycle)` exactly as today. Step 6 never appends a second
> suffix to a line it copied verbatim.

Exact wording is at the authoring session's discretion (prose, not code),
but the paragraph MUST:
1. drop every mention of "`sha` equals this cycle's reviewed HEAD **and**
   its three counts are non-null" as a rule evaluated at step 6, and must
   not reintroduce an equivalent sha/counts condition under different
   wording,
2. name the `## Test gate` section (sourced from `gate.tests_line`) as the
   value step 6 copies when it is a counts line, falling back to running
   `autopilot verify` when that section is absent or not itself a counts
   line,
3. keep the docs-only sentinel branch (`Tests: none (docs-only)`) unchanged
   — not part of the removed rule.

**Also update SKILL.md lines 181 and 324**, which describe the record-
reading model this removes and would otherwise contradict the new step-6
contract:
- **Line 181** ("step 6 ... reuses that record instead of running the suite
  again") → restate as: `review-stage` writes `last-verification.json` at
  HEAD through the same `verification.run_gate()` `autopilot verify` also
  wraps (keep this clause — it stays true, `run_gate` is still the writer);
  drop only the "step 6 reuses that record" clause and replace it with:
  step 6 takes its `Tests:` line from step 3's `gate.tests_line` (the
  `## Test gate` context section), which `review-stage` already derived
  through `reuse_verdict`; step 6 makes no reuse decision of its own.
- **Line 324** ("Omit on the live path — test counts do not exist until
  step 6") — this line documents a *shadow-run* substitution
  (`CONSENSUS_ENGINE == "shadow"`, SKILL.md:428) where the workflow's
  `review_markdown` carries a literal `{{TESTS_LINE}}` token that step 8
  (not step 5) substitutes with the line step 6 composed. That contract is
  **unaffected by this PRD** — step 6 still composes the line (now by
  copying `gate.tests_line` instead of re-deriving it), step 8 still
  performs the substitution exactly as today. Reword only
  to say the counts are decided by step 3 and composed into the `Tests:`
  line at step 6, not "do not exist until step 6" (which is no longer true
  once step 3 computes `gate.tests_line`) — but do not touch the
  `{{TESTS_LINE}}` substitution mechanism itself, which this PRD does not
  change.

The prose test (`test_tests_line_source_prose.py`) pins facts 1-2 against the
live SKILL.md text (see Test strategy outline): it asserts the step-6
section does not pair `last-verification.json` with a `sha`-equality
condition as a reuse test, and that it names `gate.tests_line` / the
`## Test gate` section as the source step 6 copies when present and
counts-shaped.

## Data flow

Before: `review-stage` (step 3) computes `gate.tests_line` via its own
`reuse_verdict` call → written to the staged context → step 6 **ignores it**
and re-derives a verdict from `last-verification.json`'s raw `sha`/counts →
two verdicts can disagree (the bug).

After: `review-stage` (step 3) computes `gate.tests_line` → step 6 **reads
the `## Test gate` section directly** and copies it verbatim when it is a
counts line (`TESTS_RE`-matching: reused, suite-run, or timeout); it falls
back to running `autopilot verify` itself only when that section is absent
or holds a non-counts line (dirty/counts-unavailable/failed-to-run). One
verdict, one source.

For the command-identity fix: `autopilot verify "bash ./gate.sh"` →
`normalize_command` now returns `"bash ./gate.sh"` unchanged (collapsed
whitespace only) → `_write_record` stores that exact string → a later
`reuse_verdict` call for `"./gate.sh"` or `"gate.sh"` normalizes to a
different string → `_record_shape_ok`'s equality check fails → `"stale"`.

## Reuse inventory

- `skills/run-autopilot/cli/verification.py:290-370` — `_record_shape_ok` and
  `reuse_verdict` already implement the ancestor/clean/command-match rule
  this PRD keeps; only `normalize_command` (lines 310-320) changes. Nothing
  else in this file needs touching.
- `skills/run-autopilot/cli/verification.py:373-390` — `_write_record`
  already calls `normalize_command` before storing; no new write path needed.
- `skills/review-work-completion/SKILL.md` step 3 — `review-stage` already
  populates `gate.tests_line` in the staged context (confirmed:
  `references/output-formats.md` documents `gate.tests_line` as "this
  cycle's computed counts"); step 6 just needs to consume what already
  exists rather than recomputing.
- Greps run: `rg -n "normalize_command|_write_record|reuse_verdict"
  cli/verification.py` (found all three, see above);
  `rg -n "tests_line|gate.tests_line" skills/review-work-completion/SKILL.md`
  (found the existing `gate.tests_line` production site at step 3/step 6
  boundary, confirming it is already computed and just unused by step 6);
  `rg -n "bash_dot_slash" cli/test_verification_dirty.py` (found the one
  test this PRD's task 1 must retarget,
  `test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces`
  at line 426).

## Alternatives considered

1. **Smallest-diff: delete the stripping in `normalize_command` only, leave
   step 6's prose rule in place.** Rejected as the sole fix — it closes
   packet 9 but leaves packet 8's two-verdicts bug (the `review-stage` says
   `reused` / session runs `verify` anyway case) unresolved, which is the
   PRD's primary success metric. Still, this is literally this design's
   Phase 0 first task, done as its own independently-landable step.
2. **Make step 6 call `reuse_verdict` itself a second time instead of
   reading `gate.tests_line`.** Rejected: re-running the same decision twice
   at step 3 and step 6 is exactly the duplication the PRD exists to
   collapse (two call sites, two chances to drift again); reading step 3's
   already-computed `gate.tests_line` is the smaller, drift-proof diff.
3. **Chosen: narrow `normalize_command` to whitespace-only, and make step 6
   a pure consumer of `gate.tests_line`.** This is the PRD's own two
   features taken together — minimal code diff (one function body, one
   prose paragraph), and it is the only option that closes both packets.
   The "extra size" over option 1 buys packet 8's fix, which is half the
   PRD's stated success metrics.

## Risks & edge cases

- **The `## Test gate` section can be legitimately absent** — only on a
  standalone (non-autopilot) run that never invoked `review-stage` at all
  (`--gate-command` is `required=True` on the CLI, so an autopilot run
  always produces the section). Step 6 must still run `autopilot verify`
  itself in that case; this is explicit in the PRD's own feature text and
  carried into the Interfaces section above. A design that silently skipped
  verification when the section is absent would be a regression.
- **A fallback `autopilot verify` run can itself return no counts** (a
  dirty tree, or no parseable summary line) — the same conditions that
  produced the original non-counts `gate.tests_line` are likely still true
  moments later. This is not a new failure mode: it is exactly today's
  existing "no record written, no `Tests:` counts to show" outcome
  (`work/references/final-verification.md` § Recorded verification result),
  unchanged by this PRD. Step 6 writes no fabricated `Tests:` line in that
  case and the cycle proceeds exactly as it does today when verification
  cannot produce one — this design introduces no new handling here, it only
  stops step 6 from copying an ungateable line forward instead.
- **Likely next change 1**: a project whose gate command is itself invoked
  with varying working directories (e.g. `(cd subdir && ./gate.sh)`) is not
  covered by whitespace-only normalization and will also be treated as
  distinct from a cwd-relative spelling — correctly, since cwd changes the
  command's actual behavior too. This design does not box that in; the
  narrower `normalize_command` generalizes cleanly to "textually identical
  modulo whitespace," which is the correct invariant for any future
  spelling-equivalence question.
- **Likely next change 2**: the CHANGELOG/prose correctness requirement
  (Phase 1 task) is a point-in-time fix; a future PRD touching
  `normalize_command` again must remember to re-sync both CHANGELOG line 44
  and `final-verification.md`'s "as run" sentence, since nothing enforces
  that synchronization structurally (it's an `rg` pin, not a type check).
  Noted as a documentation-drift risk, not fixed here — out of this PRD's
  scope.
- **Likely next change 3 (named in the PRD's own Risks section)**: the
  Phase 1 CHANGELOG/doc changes stop `bash dev/bin/release-checks` and
  `dev/bin/release-checks` from sharing a verification record — any session
  that was relying on that cross-spelling reuse for speed will see a full
  rerun (~220s) the first time its spelling changes. This is the PRD's own
  accepted tradeoff (its Risks section says "Accepted by the operator");
  this design does nothing to soften it, matching the PRD.
- **Edge case**: `normalize_command` receiving a non-str (the existing `if
  not isinstance(command, str): return ""` guard) is preserved verbatim —
  not touched by this narrowing.
- **No step-6-time HEAD re-check**: the removed prose rule re-checked
  `sha == reviewed HEAD` at step 6 time; the new rule trusts the line step 3
  computed with no re-check at step 6. A commit landing between step 3 and
  step 6 (a carry-forward edit, or a foreign commit — this checkout's own
  project capsule records a concurrent session committing mid-run before)
  would let a `(suite run this cycle)` line stand for an older HEAD. This
  is accepted as out of scope: it existed identically before this PRD
  (`review-stage`'s `reuse_verdict` already captures HEAD once at step 3
  and nothing re-checks it before step 8 writes the file today), and
  narrowing/removing the step-6 reuse rule does not make it worse — it is
  a pre-existing gap in the step 3→8 pipeline, not introduced here.
- **One-time reuse miss after upgrade**: a `last-verification.json` record
  already on disk, written under the old stripping `normalize_command`,
  stores the stripped form (e.g. `"gate.sh"` for a run invoked as
  `"bash ./gate.sh"`). The first `reuse_verdict` call after this change ships
  normalizes the live gate command without stripping, so it no longer
  matches that old stored string, and the gate reruns once (~220s) even
  though nothing about the command actually changed. This is a one-time
  format-migration cost, not a recurring one — the next record written is
  already in the new form. Accepted, same as the PRD's own named
  spelling-drift tradeoff; call it out in the CHANGELOG entry (Phase 1 task)
  so an operator seeing one unexpected rerun post-upgrade recognizes why.

## Test strategy outline

- `skills/run-autopilot/cli/test_verification_dirty.py`:
  - Retarget `test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces`:
    keep its extra-whitespace case asserting `"reused"`; change its
    `bash ./gate.sh` vs `gate.sh` case to assert `"stale"` (distinct
    spellings no longer share a record).
  - Add `test_sh_and_bash_records_do_not_cross_reuse`: a record written for
    `"sh shdep.sh"` is `"stale"` under `reuse_verdict` for `"bash
    shdep.sh"`.
  - Add `test_dot_slash_and_bare_records_do_not_cross_reuse`: a record
    written for `"bash ./gate.sh"` is `"stale"` under `reuse_verdict` for
    both `"./gate.sh"` and `"gate.sh"`.
  - Confirm `test_verification.py::test_reuse_is_stale_when_the_gate_command_differs`
    (pre-existing, unrelated command-mismatch case) still passes unmodified.
- `skills/review-work-completion/scripts/test_tests_line_source_prose.py`
  (new): a prose-pin test over the live `SKILL.md` text, both tests scanning
  only the step-6 section's text (from its `**Compose the ...**` heading to
  the next `**` step heading) —
  `test_step_6_composes_from_gate_tests_line` asserts that slice names
  `gate.tests_line` (or the `## Test gate` section it populates) as the
  value step 6 copies when present and counts-shaped;
  `test_step_6_has_no_sha_counts_reuse_rule` asserts that slice matches no
  sha-equality-as-reuse-condition pattern (e.g. a regex combining `sha` with
  `equals`/`==`/`matches` and `HEAD`) — a bare, non-conditional mention of
  `last-verification.json` elsewhere in the slice (e.g. "the sole writer
  of...") must NOT trip the test; only a sha-equality condition gating reuse
  does, so a rephrasing of the old rule under different words still fails
  it. Register this file in `dev/bin/release-checks`'s `[checks]` block
  (PRD's own acceptance criterion names this explicitly).
- Phase 1 prose checks are `rg` pins against `CHANGELOG.md`, run as the
  Phase 1 Exit Criteria `rg` commands already specify — no new test file.
- Phase-level exit criteria (already given verbatim in the PRD, unchanged by
  this design):
  - Phase 0: `uv run --no-project --with pytest python -m pytest -q
    skills/run-autopilot/cli/test_verification.py
    skills/run-autopilot/cli/test_verification_dirty.py
    skills/review-work-completion/scripts/test_tests_line_source_prose.py`
    exits 0.
  - Phase 1: `bash dev/bin/release-checks` exits 0 with `FAIL 0`.

## Review log

- non-blocker: the prose-pin test should assert absence of the sha/counts
  pairing, not one exact sentence, so a rephrasing cannot silently reinstate
  the old rule. Addressed above (Interfaces & contracts, prose test note).
- non-blocker: existing on-disk verification records written under the old
  stripping normalizer go stale once, forcing one unavoidable rerun after
  upgrade. Addressed above (Risks & edge cases).
- question: whether the `(reused ...)/(suite run this cycle)` suffix rule
  still applies at step 6 after the change, risking a double suffix.
  Addressed above (step 6 copies `gate.tests_line` verbatim including its
  suffix; the fallback path composes its own, never both).
dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 1
- non-blocker: no step-6-time HEAD re-check between step 3 and step 8.
  Addressed above (Risks & edge cases) — accepted as a pre-existing gap,
  unchanged by this PRD.
- non-blocker: the SKILL.md:181/:324 rewrites were named but unspecified,
  and :324 in particular feeds the shadow-run `{{TESTS_LINE}}` substitution.
  Addressed above (step 6 prose contract, the two dedicated bullets for
  lines 181 and 324) — the shadow mechanism itself is explicitly untouched.
- question: whether the prose-pin test's "no sha-equality pairing" check is
  a reliable substring test given that step 6 legitimately still mentions
  `last-verification.json` elsewhere (e.g. "it is the sole writer of...").
  Addressed above (Test strategy outline: the test is defined as pairing
  `last-verification.json` with a sha-equality *condition*, not bare
  co-occurrence of the two tokens).
dispatch 2 (claude-fallback, codex unavailable): cardinal-sin 0, blocker 2, non-blocker 2, question 1
- blocker: Data flow's "After" paragraph and the Risks section still
  described the superseded "falls back only when gate.tests_line is
  absent" rule and the impossible "review-stage ran without --gate-command"
  cause, contradicting the Interfaces fallback rule fixed after dispatch 2.
  Fixed above (Data flow, Risks & edge cases).
- non-blocker: the design never said what step 6 does if the fallback
  `autopilot verify` also returns no counts. Addressed above (Risks & edge
  cases): no fabricated line, unchanged from today's existing behavior.
- non-blocker: the SKILL.md:324 rewording named step 6, not step 8, as the
  `{{TESTS_LINE}}` substitution site. Fixed above (step 6 prose contract,
  Line 324 bullet).
- question: should the reworded SKILL.md:181 drop the (still-true) clause
  that `review-stage` writes `last-verification.json`? Resolved: keep it,
  drop only the reuse-at-step-6 clause. Fixed above.
dispatch 3 (claude-fallback verification, codex unavailable): cardinal-sin 0, blocker 1, non-blocker 4, question 1
result: ok
