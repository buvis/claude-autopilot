# Design: Stage and close review cycles in code

## Architecture fit

This lands entirely in the existing `skills/run-autopilot/cli/` package, alongside
`gate.py`, `rework_groups.py`, and `statectl.py` — the same layer that already
turned `enter` (PRD 00201) and `frontmatter` into code. State mutation still
goes exclusively through `statectl.do_set`/`do_append`/`do_task_add` inside one
`state.transaction()` call; the review-file shape check stays `cli/gate.py`'s
existing `run_gate()` (unchanged); `review_stage.py` wraps the existing
`gather-context.sh` and `render_prompt.py`; `review_close.py` wraps the
existing `rework_groups.group()` and `statectl` mutators. `verification.py` is
genuinely new logic — no module owns `last-verification.json` today (it is a
Write-tool artifact written by the work phase's final-verification step and
read by SKILL.md step 6's prose) — so `verification.run_gate()` becomes a
*second*, review-scoped writer of the same file shape, used only when the
review phase itself needs a fresh run.

**Naming note (corrects an internal collision in the first draft):** `cli/gate.py`
already exports a function named `run_gate()` — it is the *review-file shape
check* (`autopilot gate --review-file ...`), unrelated to running the test
suite. This design's `verification.run_gate()` is a *different* function in a
*different* module that runs the project's test command. The two are never
confused in code (different modules, different signatures), but every mention
below says `gate.run_gate` (the shape check) or `verification.run_gate` (the
test runner) explicitly to avoid the ambiguity that caused two blocking
findings in dispatch 2.

The skill prose (`review-work-completion/SKILL.md`, `phase-review.md`) becomes
a thin caller: it still issues the reviewer dispatch message itself (Agent and
background Bash calls, since the CLI cannot launch subagents), but every file
write and every state mutation around that dispatch moves into the three new
verbs.

## Module placement

New files:
- `skills/run-autopilot/cli/verification.py`
- `skills/run-autopilot/cli/review_stage.py`
- `skills/run-autopilot/cli/review_close.py`
- `skills/run-autopilot/cli/test_verification.py`
- `skills/run-autopilot/cli/test_review_stage.py`
- `skills/run-autopilot/cli/test_review_close.py`
- `skills/run-autopilot/cli/fixtures/` — golden prompt fixtures for the
  render-roster tests. Four of the five (`alice`, `bob`, `blake`, `carl`) are
  copied from the real `docs/dev/tmp/{agent}-prompt-00244c1.md` artifacts
  already on disk. **No real Eve artifact exists for that cycle** (confirmed:
  `rg --files docs/dev/tmp -g 'eve-prompt-00244*'` finds nothing) — the Eve
  fixture is instead hand-built by Phase 1's render-roster task from Eve's
  persona file (`agents/eve.md`) plus the exact per-persona substitution table
  below, and checked by a human reviewer during that task's own review pass
  before being frozen as a golden file. This is flagged explicitly rather than
  silently assumed, per dispatch 2's non-blocking finding.

Edited files:
- `skills/run-autopilot/cli/__main__.py` — register `review-stage` and
  `review-close` subcommands in the **`_SUBCOMMANDS` dict** (the real registry
  name; the first draft said `COMMANDS`, which does not exist in this file),
  same pattern as the `"group-rework": (_add_group_rework, _run_group_rework)`
  entry.
- `skills/review-work-completion/SKILL.md` — steps 3-5 replaced per Phase 2;
  step 6 (consolidate findings into the table) and step 8 (save the review
  file) stay exactly as they are today — model-executed judgment, unchanged.
  **Step 7 (today's hand-built `task-add` loop for 🟠/🟡 follow-ups) is
  DELETED outright**, not left "unchanged" (a self-contradiction in an
  earlier revision of this doc, caught by dispatch 3, said both things at
  once). Its task-creation role folds into the single `review-close
  --batch-id decision-gate` call in `phase-review.md`'s decision gate, which
  now runs after Phase 5 classification and handles BOTH the CRITICAL
  rework tasks (today's Phase 6 "Dispatch rework") and the 🟠/🟡 follow-up
  tasks (today's step 7) in one call per cycle — see "Close-out timing" and
  "Classification mapping" below.
- `skills/run-autopilot/references/phase-review.md` — the Phase 6 "Dispatch
  rework" task-creation block and the Tail sweep block each call
  `review-close` with their own `--batch-id` (see "The findings block" below).

No change to `skills/review-work-completion/scripts/gather-context.sh`,
`skills/work/scripts/render_prompt.py`, `skills/run-autopilot/cli/gate.py`
(zero new flags — see "Findings/table agreement" below for why
`--assert-findings-match-table` was dropped), `skills/run-autopilot/cli/rework_groups.py`,
`skills/run-autopilot/cli/statectl.py`, `skills/review-work-completion/scripts/replay_tests_against_base.py`,
or `skills/review-work-completion/references/agent-registry.md` — all are
called, not modified.

## Interfaces & contracts

### `verification.py`

```python
def reuse_verdict(record: dict | None, repo_root: Path, head_sha: str) -> tuple[str, dict]:
    """
    record: the parsed contents of last-verification.json, or None if the
        file is missing/unreadable/unparseable.
    Returns ("reused", record) only when ALL hold:
      - record is not None, record["sha"] is a non-empty str
      - record["passed"], record["failed"], record["skipped"] are all
        present and not None
      - `git merge-base --is-ancestor <record["sha"]> <head_sha>` exits 0
        (record["sha"] is a real ancestor of head_sha — rejects a record
        from a sibling or descendant commit surviving a reset/rebase)
      - every path in `git log <record["sha"]>..<head_sha> --name-only`
        (cwd=repo_root) starts with "docs/dev/project-management/" (an empty
        diff also counts — vacuously true)
      - `git status --porcelain` (cwd=repo_root) is empty — reuse never
        certifies a dirty working tree, since gather-context.sh's diff is
        against the working tree, not just HEAD
    Returns ("stale", {}) otherwise, including when any git call itself
    fails (missing sha, unknown ref, non-git repo, non-zero exit on the
    ancestor check) — fail toward re-running the gate, never toward
    skipping it.
    """

GATE_TIMEOUT_S = 1800  # ponytail: fixed budget, matches the batch session's
                        # own order of magnitude; raise via one constant if a
                        # project's gate command genuinely needs longer.
GATE_OUTPUT_CAP = 2_000_000  # bytes of combined stdout+stderr kept; a hung
                              # or runaway command is truncated, not read
                              # forever into memory.

def run_gate(command: str, cwd: Path, sha: str, cycle: int | None) -> dict:
    """
    Runs `command` (the project's test-gate command, e.g.
    `dev/bin/release-checks` — resolved by the caller, never hardcoded here)
    via subprocess.run(command, shell=True, cwd=cwd, capture_output=True,
    text=True, timeout=GATE_TIMEOUT_S), with stdout/stderr each truncated to
    GATE_OUTPUT_CAP bytes before any parsing or storage.
    On subprocess.TimeoutExpired: kills the process group, returns
    {"passed": None, "failed": None, "skipped": None, "exit": None,
     "raw_line": None, "timed_out": True} and writes NOTHING to
     last-verification.json (a timed-out run proves nothing; the caller's
     Tests: line reads "suite timed out after 1800s, treated as failed").
    On a clean exit, parses the command's own final summary line via the
    fixed pattern `PASS (\\d+) FAIL (\\d+) SKIP (\\d+) EXIT (\\d+)`
    (case-sensitive, matched against the LAST matching line in the captured
    stdout). Returns {"passed": int, "failed": int, "skipped": int,
    "exit": int, "raw_line": str, "timed_out": False}.
    If no line matches, returns the same shape with passed/failed/skipped
    = None (the caller's existing "could not extract -> treat as needing a
    fresh look" fallback still applies, unchanged from today).
    On a successful parse (passed/failed/skipped all not None), WRITES
    last-verification.json: {"sha": sha, "cycle": cycle, "commands":
    [{"command": command, "exit": result["exit"]}], "passed", "failed",
    "skipped"} — same shape `skills/work/references/final-verification.md`
    already defines, so a review-triggered run and a work-phase run are
    indistinguishable to any reader of the file. This is the SOLE additional
    writer introduced by this PRD; the work phase's own final-verification
    write (unrelated call site, end of the work loop) is untouched.
    """
```

`run_gate`'s one-line-summary parsing is what makes "no second run is ever
needed to read counts" (PRD Success Metric) true — it both runs the command
*and* records the result in one call, instead of today's two-pass pattern
(run once to see output, run again because `last-verification.json` was
stale or the count couldn't be read the first time).

### `review_stage.py`

```python
def stage(
    cycle_id: str,
    tasks: list[dict],              # from state.tasks, or from a
                                     # standalone caller's own plan
    prd_path: Path,
    design_doc: Path | None,
    roster: list[str],              # persona names, already resolved by the
                                     # caller — see "Roster is persona names,
                                     # not lens names" below
    repo_root: Path,
    gate_command: str,
    replay_cmd: str | None,         # the per-file pytest invocation
                                     # SKILL.md step 3(c) already resolves
                                     # (unchanged resolution; stage() takes
                                     # it as a parameter rather than
                                     # re-deriving it, so a project with no
                                     # pytest replay convention just passes
                                     # None and the replay step is skipped,
                                     # matching today's skip behavior)
    since: str | None = None,
    state_path: Path | None = None,  # None => standalone mode, see below
    settled_ledger: Path | None = None,
) -> dict:
    """
    Standalone mode (state_path is None): tasks/prd_path/design_doc/roster
    are supplied directly by the caller (a standalone
    `/autopilot:review-work-completion` run reading them from the PRD and
    its own task list, exactly as today's prose does when no state.json
    exists) — PRD line 44 names standalone runs as a target user, so this
    is required, not optional. Steps 9 (arm the roster / state write) is
    SKIPPED in this mode: there is no state.json to stamp and no dispatch
    rows keyed to a batch. Every other step (1-8 below) runs identically.

    Autopilot mode (state_path given): same steps, plus step 9.

    1. Write docs/dev/tmp/review-tasks-{cycle_id}.md from `tasks` (one row
       per task; folded/shared-commit tasks keep their own row with commit
       SHA + companion IDs — same shape as today's SKILL.md step 3(a)).
    2. Write docs/dev/tmp/review-prd-{cycle_id}.md: the PRD summary from
       `prd_path`, plus, when `design_doc` is given and exists, its full
       content appended under "## Design Doc".
    3. Invoke gather-context.sh as a subprocess:
       ["bash", ".../gather-context.sh", *(["--since", since] if since else []),
        "docs/dev/tmp/review-tasks-{cycle_id}.md",
        "docs/dev/tmp/review-prd-{cycle_id}.md"]
       capturing the two paths it prints (review-context-{id}.md,
       review-diff-{id}.diff) and the diff-range base sha it resolved
       (parsed from its own stdout/the context file's header — unchanged
       from today's convention). Exit 3 (empty diff / no base branch, the
       00237 guard) propagates as stage()'s own non-zero return with that
       stderr text intact (see Risks & edge cases) — never retried here.
    4. Append, in order, to review-context-{cycle_id}.md:
       compute_mech_facts.py output, detect_tautological_tests.py output,
       and — only when `replay_cmd` is not None — replay_tests_against_base.py
       --base <the diff-range base sha from step 3> --cmd "<replay_cmd>"
       (the PER-FILE pytest invocation, never `gate_command`: these are two
       distinct commands with two distinct purposes, a conflation dispatch
       2 flagged as blocking in the first draft). `replay_cmd is None` skips
       this sub-step entirely and appends nothing for it, matching the
       script's own existing skip-and-say-so behavior when nothing fits.
    5. Append the settled-decisions ledger section (`settled_ledger`'s
       contents, when given) and the `engram pack` block (substituting
       {PACK_FILE}/{PACK_FINDINGS}; a pack failure is recorded as
       "pack: failed (<reason>)" in the returned summary dict and never
       raises; "not inside a registered repo" names `gita add` in the
       reason, matching today's exact wording).
    6. Call verification.reuse_verdict() + (when stale) verification.run_gate(
       gate_command, repo_root, sha=<HEAD>, cycle=<cycle_id's cycle number,
       or None in standalone mode>), and append the resulting Tests: line
       text to the context file's mechanical-facts block so every reviewer
       prompt sees one gate verdict already computed, with the same suffix
       convention `cli/gate.py`'s `TESTS_RE` already accepts
       ("(reused from last-verification.json at <sha7>)" or
       "(suite run this cycle)" or "(suite timed out after <n>s, treated as
       failed)").
    7. Call render_roster(context_file, diff_file, prd_file, pack, ledger,
       prior_findings, roster) (below).
    8. PERSONA PREFLIGHT, run before any render_prompt.py invocation for
       each roster member: read ${CLAUDE_PLUGIN_ROOT}/agents/<name>.md,
       confirm it opens with a `---`-delimited YAML block, parse that block,
       and confirm it has non-empty `name`, `description`, and `tools` keys
       (agent-registry.md's own mandatory-field convention). A missing file,
       a missing/malformed frontmatter block, or an absent required key
       marks that persona FAILED in the returned prompts dict ({name: None})
       WITHOUT calling render_prompt.py at all — this is the fail-closed
       check PRD's error case needs; render_prompt.py itself does not
       provide it (`_strip_frontmatter` only checks for a closing
       delimiter, not key presence — a gap dispatch 2 confirmed by reading
       the function). A persona that passes preflight still goes through
       render_prompt.py's own placeholder-coverage check (its existing
       `PLACEHOLDER_RE`/exit-1 behavior), which is a second, independent
       fail-closed layer render_stage does not duplicate.
    9. (Autopilot mode only.) Stamp state.review_lenses: for each ACTIVE
       LENS (`consensus`, `blind`, `doubt`, plus `ui`/`fable` when active —
       see "Roster is persona names, not lens names" below for the
       lens<->persona mapping this step consumes in reverse) whose personas
       all rendered successfully, set state.review_lenses[lens] = "running";
       a lens with a failed persona is recorded as "running" too (matching
       today's behavior — failure is discovered at consolidation, not at
       stage time) via one statectl.do_set(state, parse_path("review_lenses"), {...})
       call (full replace of the dict, same as today's prose). Then open one
       CLI dispatch row per CLI reviewer actually in the roster
       (bob and/or carl) via record_dispatch.py start --kind bob|carl
       --task review-{cycle_id} --prompt-file <path>, best-effort (a failed
       dispatch-row open is logged to the returned summary, never raised —
       record_dispatch.py is already a best-effort telemetry sink elsewhere
       in this codebase, e.g. the Session handoff procedure's `leave` row).
    Returns one JSON-serializable summary dict: {"mode": "standalone"|"autopilot",
      "tasks_file":..., "prd_file":..., "context_file":..., "diff_file":...,
      "pack": "ok"|"failed (<reason>)",
      "gate": {"verdict": "reused"|"stale", "tests_line": str, "timed_out": bool},
      "prompts": {"alice": "docs/dev/tmp/alice-prompt-{id}.md", ...,
                  "<failed-persona>": None},
      "dispatch_rows": {"bob": "<id>"|None, "carl": "<id>"|None},
      "elapsed_s": float}
    Printed as one JSON line on stdout (the "timing row" Success Metric 1
    measures against) and returned as a dict for Python callers/tests.
    """

def render_roster(
    context_file: Path, diff_file: Path, prd_file: Path,
    pack_file: Path | None, settled_ledger: Path | None,
    prior_findings: Path | None, roster: list[str],
) -> dict[str, Path | None]:
    """
    roster: PERSONA NAMES (alice, bob, blake, carl, eve) — never lens names.
    Dispatch rows and state.review_lenses use lens names; render_roster
    works entirely in persona names, resolved by the caller via this fixed
    table (copied from today's SKILL.md step 5 and agent-registry.md, not
    invented):
      lens "consensus"  -> personas [alice, bob, carl]
      lens "blind"      -> persona  [blake]
      lens "doubt"      -> persona  [bob]   (codex doubt_reviewer) OR
                                     [eve]   (fable doubt_reviewer, PLUS bob
                                              still runs as part of consensus)
      lens "fable"      -> persona  [eve]   (same persona as the doubt=fable
                                              case above; "fable" is the lens
                                              key state.review_lenses uses
                                              when Eve is the 5th lens)
    (`ui`, referenced in agent-registry.md's broader 13-persona roster, maps
    to Carl in other skills but review-work-completion's roster has no
    separate "ui" lens of its own — Carl is covered by "consensus" here;
    callers constructing `roster` for review_stage.stage() de-duplicate by
    persona name, so Carl appears once even though two lens keys could
    theoretically name him.)

    Per-persona --set table for render_prompt.py (verbatim from
    agent-registry.md's substitution table and SKILL.md step 4's existing
    per-persona instructions — this draft corrects the first version's
    Blake/Bob/Eve omissions):
      alice, bob, carl: {CONTEXT_FILE}=context_file, {DIFF_FILE}=diff_file,
        {DIFF}=<diff_file's content, inlined>, {PACK_FILE}=pack_file (or the
        literal "none" when absent), {PACK_FINDINGS}=<pack's findings
        section or "none">, {PRD}=prd_file, plus the settled-decisions
        section appended (from settled_ledger) when present.
      bob (doubt lens only, i.e. when doubt_reviewer resolved to "codex"):
        ADDITIONALLY appends eve.md's "Two lenses" and "Rubric verdicts"
        sections verbatim (read from agents/eve.md, not re-authored) plus
        the FIX/VERIFY/KNOWN bucket section (agent-registry.md's existing
        text for this), per the PRD's explicit requirement.
      blake: {PRD}=prd_file, {RUBRIC}=<review-blindly/references/rubric.md
        content>, {OUTPUT_FORMAT}=<blake.md's own OUTPUT_FORMAT section
        content, read from the same persona file> — Blake's persona file
        (agents/blake.md) declares {OUTPUT_FORMAT} itself, so render_prompt.py
        would exit 1 (missing placeholder) if this --set were omitted; the
        first draft's "{PRD}, {RUBRIC} only" was incomplete and is corrected
        here. NEVER {DIFF_FILE}/{DIFF}/the ledger — Blake stays diff-blind.
        Gains the "## Filesystem notes" block appended to its run inputs
        (not a {PLACEHOLDER}) when this project's trigger holds.
      eve: {PACK_FINDINGS}=<pack's findings-precedent section>, plus (as
        run-input appends, not placeholders, matching agents/eve.md's own
        five-run-input convention from references/agent-invocation.md) the
        PRD, diff range, changed-file list, the pack's findings-precedent
        section, and the two mechanical test-check blocks (mech facts +
        tautology detector output) from the context file.
      every persona, when `prior_findings` is given (incremental cycle):
        appended prior cycle's consolidated findings plus the fixed
        incremental instruction paragraph from SKILL.md step 4 — EXCEPT
        blake, which never receives it (blind every cycle, incremental or
        not).

    For each name in roster: run the PERSONA PREFLIGHT (stage() step 8)
    first; on pass, shell out to render_prompt.py <persona> --out
    docs/dev/tmp/{name}-prompt-{id}.md with the --set/--set-file table
    above. A preflight failure, or a non-zero render_prompt.py exit (its
    own placeholder-coverage check), marks {name: None} in the returned
    dict without raising, so the other personas still render.
    Returns {name: Path | None}.
    """
```

### `review_close.py`

```python
def close(
    review_file: Path,
    state_path: Path,
    batch_id: str,          # "decision-gate" or "tail-sweep" — see
                             # "Close-out timing" below; distinguishes the
                             # two call sites so each cycle's two close()
                             # calls (if both run) are independently
                             # idempotent rather than racing one shared flag
    chosen_findings: list[dict],   # the findings THIS call applies — the
                                    # model has already classified them
                                    # (fix/defer/discard/verify) before
                                    # calling close(); close() never
                                    # re-decides, it only applies
) -> dict:
    """
    1. Run cli.gate.run_gate(review_file, reviewers=<from review file
       frontmatter>, require_codex_guard=<caller-decided>) — IMPORTED
       (same package), not subprocess. Non-zero -> return
       {"applied": False, "reason": "<gate failure text>"} and open NO
       transaction (nothing written).
    2. Resolve a canonical review identity:
       str(review_file.resolve()) + "::" + batch_id — this is the key
       idempotency below checks, so a relative-vs-absolute alias of the
       same file, or the same file under two different batch_ids, is
       handled correctly (relative paths no longer silently bypass the
       idempotency check, correcting the first draft).
    3. Call statectl.mutate(state_path, _apply) — the SAME compound-verb
       entry point every other statectl verb uses (`do_task_add`,
       `task-done`, etc. are all thin wrappers around one `mutate()` call),
       not a bare `state.transaction()` with its unscoped default
       validator. `mutate()` supplies the scoped
       `validator=lambda new_state: schema.validate_changed(before, new_state)`
       internally, so `close()` gets the same before/after-diff validation
       discipline as every other writer in this package — this draft
       corrects an earlier version that named `state.transaction()` directly
       without saying which validator it would run under (flagged by
       dispatch 3). `_apply(state)` is a local closure performing steps
       4-9 below as in-memory mutations on the `state` dict `mutate()`
       hands it, returning the dict `mutate()` will validate and persist.
       Inside `_apply`:
       a. Read state.applied_review_batches (a new state.json list field).
          If the canonical identity from step 2 is already in it, abort the
          transaction with no writes and return
          {"applied": False, "reason": "already applied"}.
       b. For `chosen_findings` entries the caller marked "fix" (CRITICAL
          or otherwise — close() groups whatever severities the caller
          handed it; which severities go through which call site is a
          phase-review.md/SKILL.md policy choice, not close()'s to make):
          group via rework_groups.group(chosen_findings) (imported
          directly, same function `autopilot group-rework` already wraps),
          create one task per group via statectl.do_task_add (imported),
          named "[D{cycle}] <name_hint>" (decision-gate call) or
          "[D{cycle}] Tail sweep: <name_hint>" (tail-sweep call — batch_id
          supplies which prefix template applies) with a
          "### Findings (verbatim)" block, carrying `task.model` set from
          the caller-supplied `default_tier` argument (not shown above for
          brevity: close() takes `default_tier: str = "sonnet"` and passes
          it straight to the task payload, matching Phase 6's own tier
          computation, which close() does not re-derive), and collect the
          new task ids.
       c. statectl.do_append(state, statectl.parse_path("rework_task_ids"),
          <each new id>) — ALWAYS via parse_path(), never a bare field-name
          string (statectl's do_append/do_set take list[Token]; a bare str
          like "rework_task_ids" is iterated character-by-character and
          silently produces a corrupt nested path — this was a blocking
          defect in the first draft's pseudocode, caught by dispatch 2
          reading statectl.py's actual signature).
       d. For `chosen_findings` entries marked "defer": statectl.do_append(
          state, parse_path("deferred_decisions"), <one entry per finding,
          shape matching phase-review.md's existing classification table>).
          For entries marked "verify" or "discard": no state.json task
          effect (verify-routed findings get their own check file per the
          existing Gate reuse / Tail-sweep-exclusion convention; discarded
          findings are recorded in the audit log by the caller's existing
          `autonomous_decisions`/`deferred_decisions` append, not by close()
          inventing a third list).
       e. statectl.do_set(state, parse_path("doubts_rubric_verdicts"),
          <parsed from the review file's Bob's/Eve's D{n}: pass|fail
          lines>) — full replace, same as today, ALWAYS via parse_path().
       f. statectl.do_set(state, parse_path(f"review_lenses.{lens}"),
          "done"|"failed") for each lens this review file's frontmatter
          names as available/unavailable — one call per lens, each via
          parse_path (`review_lenses.consensus`, not a bare string).
       g. statectl.do_append(state, parse_path("applied_review_batches"),
          <the canonical identity from step 2>). `applied_review_batches`
          is added to `cli/schema.py`'s `_LIST_FIELDS` tuple (a one-line
          addition, same pattern as `deferred_decisions`) so a malformed
          write is caught by `validate_changed` like every other list
          field — `schema.py`'s own docstring already tolerates unknown
          fields, so this addition is for type-checking, not to avoid a
          validation failure that would otherwise occur.
    4. AFTER the transaction commits (best-effort, outside the lock — this
       is deliberate, not an oversight: `record_dispatch.py` is a JSONL
       telemetry sink elsewhere in this codebase and is never part of the
       state.json atomicity boundary; a crash between the commit and these
       calls leaves telemetry rows open, which the NEXT close() call for
       the same cycle's remaining dispatches reconciles by re-running the
       `end` call for any row its own bookkeeping still shows open — the
       dispatch ids are already in the review file's frontmatter, so this
       is a safe, idempotent retry, not silent data loss): close the CLI
       dispatch rows opened at stage time (record_dispatch.py end <id>
       <outcome-flags>, same outcome table SKILL.md step 6 uses today).
    Returns {"applied": True, "tasks_created": [...], "rework_task_ids": [...],
      "lenses_closed": {...}} or the early {"applied": False, "reason": ...}
      shapes above.
    """
```

**Close-out timing (corrects the first draft's placement, and a
self-contradiction a later draft introduced — dispatch 3 caught both the
"step 7 moves" claim in Module placement and a "steps 6-8 stay unchanged"
claim here disagreeing with it; this section is the single resolution).**
`review-close` is called at the point today's prose already creates tasks
from findings — **after** the decision-gate classification
(`phase-review.md`'s existing Classification table) has run, and **after**
a CRITICAL rework design has been written and passed its own gate
(`phase-review.md` "Dispatch rework"). Concretely: SKILL.md steps 3-5 move
into `review-stage`; step 6 (consolidate findings into the table) and step 8
(save the review file) stay exactly where they are, as model-executed
judgment calls, unchanged by this PRD; **step 7 is deleted** — its 🟠/🟡
follow-up `task-add` loop is absorbed into the decision-gate call below, run
once classification has actually happened, instead of running before
classification as it does today (today's step 7 runs before Phase 5's
classification even starts, which is itself the gap this PRD closes: a
follow-up task is currently created from the raw table, then Phase 5
classification runs its own judgment over the same findings — the two were
never actually coupled). `phase-review.md`'s task-creation call sites each
become one `review-close --review-file <f> --batch-id decision-gate|tail-sweep
--findings <chosen-findings-path>` call: the `decision-gate` call is the ONE
call per cycle that creates every task a cycle's classification produces —
both the CRITICAL `[D{cycle}]` rework tasks (today's Phase 6 "Dispatch
rework") and the 🟠/🟡 follow-up tasks (today's deleted step 7) — because
`chosen_findings` simply carries every classified finding from that cycle,
whatever its severity, and `close()` groups whatever it is handed. The
`tail-sweep` call runs once more, only at convergence, over the separate
Medium/Low tail `phase-review.md`'s Tail sweep section selects.
`doubts_rubric_verdicts` and `review_lenses` close-out happen at the
`decision-gate` call (the first one in a cycle); the `tail-sweep` call skips
those two sub-steps entirely when they are already recorded (idempotent
no-op, not a second full roster close-out).

**Classification mapping (new — this table did not exist in the prior
draft, which dispatch 3 flagged as a missing link between Phase 5's six
buckets and `close()`'s four `chosen_findings.classification` values):**

| `phase-review.md` Classification row | `chosen_findings[].classification` |
|---|---|
| Auto-fix | `"fix"` |
| Research-then-decide, verdict "proceed" | `"fix"` |
| Research-then-decide, verdict "escalate" | `"defer"` |
| Routed to verification | `"verify"` |
| Discard — contradicts computed facts | `"discard"` |
| Defer to batch end (incl. every CRITICAL) | `"defer"` |
| PAUSE (blocking escalation) | never reaches `close()` — resolved via
  `AskUserQuestion` (interactive) or the Loop-mode stall procedure (loop
  mode) BEFORE the decision-gate `review-close` call runs for that cycle;
  a paused/stalled cycle calls `review-close` with the remaining,
  already-resolved findings only, once the blocker is cleared |

### The findings block (new contract)

The review file keeps its human-readable `## Consolidated Findings` markdown
table exactly as today — the table stays the single source of truth that
reviewers, Alice's consensus pass, and a human reader all use. `review_close`
does **not** attempt to cross-validate a second, separately-authored
machine-readable block against that table (the first draft's
`--assert-findings-match-table` flag is DROPPED: comparing row counts cannot
catch a changed severity/file/issue on an unchanged-count edit, and comparing
full field equality would require either parsing the prose table — fragile —
or re-authoring both from one generator, which is a bigger PRD than this
one). Instead: **the table is the only block.** `review_close.close()`'s
`chosen_findings` argument is a plain JSON array built by the MODEL, by hand,
from the rows of the table it already produced in step 6 (consolidation) and
already classified in the decision gate — the same information the model
holds in context immediately after classifying, written once to
`docs/dev/tmp/<prd-stem>-<batch_id>-<cycle>-findings.json` with the Write
tool (exactly as today's `--findings` file for `autopilot group-rework`
already works), with each entry:

```json
{"severity": "🔴", "file": "path:line", "issue": "...",
 "classification": "fix"|"defer"|"verify"|"discard", "found_by": ["bob","carl"]}
```

`"severity"` uses the SAME EMOJI VOCABULARY `rework_groups.py` already keys
on (`🔴`/`🟠`/`🟡`/`⚪`), not an English word — the first draft's
`"severity": "critical"` would have silently fallen through
`rework_groups._CRITICAL`'s exact-string check and been treated as
non-critical, a blocking defect dispatch 2 caught by reading
`rework_groups.py`'s actual comparison. `review_close.close()` passes
`chosen_findings` straight to `rework_groups.group()` with no translation
layer, so this is the one place a wrong emoji silently misroutes a finding —
callers (the model, writing the findings JSON) are responsible for copying
the table's own emoji cell verbatim, which they already do today when
hand-building `--findings` files for `autopilot group-rework`.

## Data flow

```
PRD + (optional) state.json (tasks, review_lenses, doubt_reviewer)
     │
     ▼
review-stage --cycle-id <id> [--state <path>] [--since <sha>]
     │
     ├─> docs/dev/tmp/review-tasks-{id}.md, review-prd-{id}.md
     ├─> gather-context.sh ──> review-context-{id}.md, review-diff-{id}.diff
     ├─> verification.reuse_verdict()/run_gate() ──> Tests: line
     │        (run_gate, when it runs fresh, ALSO writes
     │        last-verification.json)
     ├─> persona preflight + render_prompt.py × N ──> {persona}-prompt-{id}.md
     └─> (autopilot mode only) state.review_lenses = {...: "running"} (write)
         + record_dispatch.py start × (bob, carl present)
     │
     ▼ (stdout JSON summary read by the model)
model issues Agent/Bash dispatch message using the summary's prompt paths
     │
     ▼
reviewers write findings ──> docs/dev/project-management/reviews/<stem>-review-{n}.md
     │  (## Consolidated Findings table — unchanged shape)
     ▼
model classifies findings (decision gate, unchanged judgment) and writes
docs/dev/tmp/<stem>-decision-gate-{n}-findings.json (chosen_findings)
     ▼
review-close --review-file <path> --batch-id decision-gate --findings <path>
     ├─> cli.gate.run_gate() shape check (refuse on failure; no writes)
     ├─> ONE state.transaction(): idempotency check, rework_groups.group() on
     │   "fix" findings -> task-add × N, rework_task_ids, deferred_decisions,
     │   doubts_rubric_verdicts, review_lenses[*]="done"/"failed",
     │   applied_review_batches
     └─> (best-effort, outside the lock) record_dispatch.py end × 2
     │
     ▼ (at convergence, later in the same cycle)
review-close --review-file <path> --batch-id tail-sweep --findings <path>
     └─> same transaction shape, scoped to the swept Medium/Low findings
```

## Reuse inventory

- `skills/review-work-completion/scripts/gather-context.sh` — called as a
  subprocess from `review_stage.stage()`, unchanged, same `--since`/path-scope
  behavior (incl. the `review-paths` marker file and the 00237 empty-diff
  exit-3 guard).
- `skills/work/scripts/render_prompt.py` — called once per roster member from
  `render_roster()`; its `PLACEHOLDER_RE`/`_resolve_assignments`/exit-1
  fail-closed behavior is reused as-is. Its frontmatter check is NOT reused
  for persona validation (confirmed by reading `_strip_frontmatter`: it only
  checks for a closing `---` delimiter, not key presence) — `review_stage`
  adds its own preflight in front of it rather than assuming the renderer
  covers that case.
- `skills/run-autopilot/cli/gate.py` (`run_gate`, `VERDICT_RE`, `TESTS_RE`,
  `_guard_matches_roster`) — imported directly by `review_close.close()` for
  the refusal check, with ZERO new flags (the originally proposed
  `--assert-findings-match-table` is dropped — see "The findings block").
- `skills/run-autopilot/cli/rework_groups.py` (`group`, `file_key`,
  `_CRITICAL`/`_RANK`'s existing emoji vocabulary) — imported directly by
  `review_close.close()`; the findings-block schema conforms to this
  vocabulary rather than inventing a translation layer.
- `skills/run-autopilot/cli/statectl.py` (`do_set`, `do_append`,
  `do_task_add`, `parse_path`, `state.transaction`) — imported directly
  (same package). Every call site in this design explicitly routes a field
  name through `parse_path()` first; none passes a bare string to `do_set`/
  `do_append`.
- `skills/run-autopilot/cli/__main__.py`'s `_SUBCOMMANDS` dict and the
  `_add_group_rework`/`_run_group_rework` registration pattern (argparse
  subparser + handler pair) — copied for `review-stage`/`review-close`
  registration.
- `skills/review-work-completion/scripts/compute_mech_facts.py`,
  `detect_tautological_tests.py`, `replay_tests_against_base.py` — called as
  subprocesses from `stage()` in the same order SKILL.md step 3(c) uses
  today; `replay_tests_against_base.py --cmd` receives the project's
  per-file pytest invocation (a `stage()` parameter, resolved by the caller
  exactly as today), never the full gate command — the two are kept
  explicitly distinct after dispatch 2 flagged their conflation.
- `skills/review-work-completion/references/agent-registry.md` — its
  substitution table and lens->persona mapping are encoded directly into
  `render_roster()`, corrected in this draft to include Blake's
  `{OUTPUT_FORMAT}`, Bob's appended Eve sections (doubt lens), and Eve's
  five run-inputs, all of which the first draft omitted.
- `docs/dev/tmp/{alice,bob,blake,carl}-prompt-00244c1.md` — copied into
  `cli/fixtures/` as golden-test inputs/expected-outputs; the Eve fixture is
  hand-built (see Module placement) since no real one exists for that cycle.
- `skills/work/references/final-verification.md`'s `last-verification.json`
  shape (`sha`, `cycle`, `commands`, `passed`, `failed`, `skipped`) — reused
  verbatim as the write shape `verification.run_gate()` produces, so the
  file has one shape regardless of which caller wrote it.
- `greps tried`: `rg "last.verification" skills/` (confirms the one prose
  writer/reader pair, no existing Python module); `rg "findings.block|machine.readable" skills/review-work-completion skills/run-autopilot` (nothing — the findings-block idea is new, and this draft resolves it by using the existing table directly rather than adding a second artifact); `rg "def .*verdict|def .*reuse" skills/` (no prior `reuse_verdict`-shaped function); `rg --files docs/dev/tmp -g 'eve-prompt-00244*'` (confirms no real Eve fixture exists for the named cycle).

## Alternatives considered

1. **(chosen) Three thin CLI verbs wrapping existing scripts/modules**, with
   `review-close` applying findings the table already carries (no second
   findings artifact), called at the existing decision-gate/tail-sweep sites
   rather than at file-save time. Cost: three new modules plus edits to two
   skill files, and a `batch_id`-scoped idempotency key instead of a single
   flag. Benefit: every piece of today's reviewed, working logic
   (gather-context.sh, render_prompt.py, gate.py, rework_groups.py) stays
   untouched; the two timing/schema corrections in this draft (vs. the first
   draft dispatch 2 rejected) come from matching the ACTUAL call sites and
   ACTUAL function signatures in the codebase, not from adding new
   mechanism.
2. **Smallest-diff version: fold `verification.py`'s two functions into
   `review_stage.py` as private helpers**, no separate module. Rejected only
   for the Phase 0 dependency ordering the PRD specifies and because
   `verification.run_gate`'s write-last-verification.json behavior is
   independently reusable (a future non-review caller could want the same
   one-call run+record). If review still prefers the merge, it is a
   20-line, net-negative-file change with no interface change for
   `stage()`'s callers.
3. **A single monolithic `review_orchestrate.py`** covering stage + close +
   verification behind one CLI verb. Rejected: `review-stage` and
   `review-close` run at wall-clock-separated points (reviewers write files
   in between, sometimes across a session handoff), and a single module
   invites hidden shared state across that gap that three files with
   explicit state.json reads avoid.
4. **A standalone `### Findings (machine)` JSON block appended to the saved
   review file** (the first draft's approach), kept in sync with the table
   by a count-comparison gate flag. Rejected after dispatch 2 showed the
   count check cannot catch a content change at an unchanged count, and a
   full field-equality check would need either a prose-table parser or a
   single shared generator for both — either is strictly more machinery than
   this PRD's stated scope. The chosen alternative (table is the only
   artifact; `chosen_findings` is authored fresh from it at classification
   time, same as today's hand-built `--findings` files) has no
   sync-drift risk because there is only one artifact to drift from.

## Risks & edge cases

- **gather-context.sh exit 3 (empty diff/no base branch)**: `review_stage.stage()`
  propagates this as a non-zero return with the stderr text intact; the
  caller's existing 00237-guard handler is unchanged.
- **A hung or runaway gate command**: bounded by `verification.GATE_TIMEOUT_S`
  (1800s) and `GATE_OUTPUT_CAP` (2MB captured output); a timeout writes
  nothing to `last-verification.json` and reports itself as a failed/timed-out
  Tests: line rather than hanging the review session indefinitely (this was
  the one cardinal-sin-level gap in the first draft: unbounded `subprocess.run`
  with no timeout on a project test command).
- **Reuse certifying a dirty or non-ancestor tree**: closed by the ancestry
  check (`git merge-base --is-ancestor`) and the working-tree-clean check
  added to `reuse_verdict()` above; both fail toward "stale" on any doubt.
- **Dispatch-row telemetry outliving a crash between the state commit and
  the `record_dispatch.py end` calls**: accepted as best-effort (matching
  this codebase's existing telemetry convention), with the specific
  recovery path spelled out in `close()`'s step 4 docstring rather than left
  implicit.
- **Likely next changes after this PRD**: (1) a future PRD may want
  `review-stage`/`review-close` to also cover the fast-track lane's
  single-cycle review — `stage()`/`close()` take explicit parameters rather
  than hardcoding `state.json`'s shape, specifically so this extension does
  not require a rewrite; standalone mode already proves the non-state.json
  path works. (2) the `applied_review_batches` list will grow across a long
  batch — acceptable at today's PRD-per-batch scale, worth capping at Phase
  9's per-PRD reset if a future PRD needs to bound state.json size. (3) a
  future PRD may want the Tail sweep's own HIGH-finding handling (today
  Medium/Low only) folded into the same `close()` call rather than kept as a
  phase-review.md-level policy choice about which severities go to which
  `batch_id` — this design deliberately leaves that choice to the caller
  (close() groups whatever it's handed) so it does not need to change if
  that policy changes.

## Test strategy outline

- `test_verification.py`: `test_reuse_when_only_store_paths_changed`,
  `test_stale_when_code_changed`, `test_stale_when_counts_null`,
  `test_run_gate_prints_one_summary_line` (PRD-specified); plus
  `test_reuse_verdict_fails_closed_on_git_error`,
  `test_reuse_verdict_rejects_non_ancestor_sha`,
  `test_reuse_verdict_rejects_dirty_tree`,
  `test_run_gate_times_out_and_writes_nothing`,
  `test_run_gate_writes_last_verification_json_on_fresh_run`.
- `test_review_stage.py`: `test_stage_writes_every_input_file`,
  `test_stage_survives_pack_failure`,
  `test_stage_stamps_roster_and_opens_cli_rows` (PRD-specified, autopilot
  mode); plus `test_stage_standalone_mode_skips_state_write`; golden tests
  `test_render_matches_golden_{alice,bob,blake,carl}` against the real
  `cli/fixtures/*-prompt-00244c1.md` fixtures, `test_render_matches_golden_eve`
  against the hand-built Eve fixture, `test_blake_prompt_carries_no_diff_or_ledger`,
  `test_blake_prompt_includes_output_format` (regression for the first
  draft's omission), `test_bob_doubt_prompt_includes_eve_sections`,
  `test_persona_preflight_fails_closed_on_malformed_frontmatter`,
  `test_replay_cmd_never_receives_gate_command`.
- `test_review_close.py`: `test_close_adds_one_task_per_group`,
  `test_close_is_idempotent`, `test_close_refuses_a_gate_failing_review_file`,
  `test_close_records_doubt_verdicts` (PRD-specified); plus
  `test_close_group_uses_emoji_severity_not_english_word`,
  `test_close_idempotency_check_is_inside_the_transaction` (two concurrent
  calls, one wins), `test_close_decision_gate_and_tail_sweep_batches_are_independently_idempotent`,
  `test_close_state_mutations_use_parse_path` (a regression test asserting
  no bare-string field name reaches `do_set`/`do_append`);
  `test_close_uses_statectl_mutate_scoped_validator` (asserts `close()` goes
  through `statectl.mutate()`, not a bare `state.transaction()` call, so it
  gets the same scoped `validate_changed` discipline as every other compound
  verb); `test_close_maps_every_classification_row_to_a_chosen_finding_value`
  (one case per row of the Classification mapping table, including that a
  PAUSE-routed finding never appears in `chosen_findings` at all).
- `test_cli_registers_review_stage_and_close` (asserts registration in
  `_SUBCOMMANDS`, PRD-specified, corrected name).
- Phase 2 prose tests: `test_skill_stages_via_review_stage` (PRD-specified),
  `test_phase_review_closes_via_review_close` (PRD-specified, asserts BOTH
  the decision-gate and tail-sweep call sites pass a `--batch-id`); existing
  `test_reviewer_dispatch_prose.py`, `test_agent_registry.py`,
  `test_review_resume_prose.py` must keep passing unmodified.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 1
dispatch 2 (codex): cardinal-sin 1, blocker 13, non-blocker 1, question 0
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 2, question 0

Dispatch 3 notes: codex's own dispatch-3 run (pid logged in
`docs/dev/tmp/design-codex-output-00249-d3.txt`) exited without a parseable
final findings report after exhausting its context gathering a second time
over the same files — treated as a codex outage per the skill's fallback
rule; a fresh Claude subagent ran the identical verification prompt instead.
It confirmed 15 of 17 prior fixes hold against the real code, and surfaced
one blocker (a self-contradiction between "Module placement" and the
original "Close-out timing" text over whether SKILL.md step 7 moves into
`review-close`) plus one implementation-choice gap (`close()`'s transaction
validator was unspecified). Both are fixed above: step 7 is deleted
outright and its task creation is folded into the `decision-gate`
`review-close` call via the new Classification mapping table; `close()` now
explicitly goes through `statectl.mutate()` rather than a bare
`state.transaction()`. A third, smaller note (whether `applied_review_batches`
needs a `schema.py` entry) is addressed with a one-line schema addition.
No cardinal sins or blockers remain open.

result: ok
