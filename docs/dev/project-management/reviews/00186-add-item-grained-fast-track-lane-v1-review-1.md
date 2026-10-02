---
prd: dev/local/prds/wip/00186-add-item-grained-fast-track-lane-v1.md
review: 1
date: 2026-09-07
head_sha: b909eb0a095134d0f722e7e6e3fea82cab9801ea
codex_thread_id: 01a07da8-a5bb-79b1-9b35-c29325da1d5a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00186-add-item-grained-fast-track-lane-v1

Diff range: `0bb137d70cdd19369bda3bfb73b7e924b4c2e3b8..b909eb0a095134d0f722e7e6e3fea82cab9801ea`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

scope note: this repo commits PRD work straight onto `master`, so `gather-context.sh`'s branch-base detection would have produced an EMPTY diff (`git diff master` while on `master`). The full-review diff was therefore scoped with `--since <work_start_sha>`, which makes the produced diff exactly the `COVERAGE_DIFF_RANGE` recorded above — the PRD's whole work range. The context file's own header consequently labels it "incremental review (changes since 0bb137d70cdd…)"; that label is cosmetic. This is cycle 1 and no prior review file exists, so no incremental addendum was added to any prompt.

verification queue: none written this cycle. Bob is the doubt lens (`doubt_reviewer: codex`, Eve not activated), and he emitted no FIX/VERIFY/KNOWN bucket structure — `agents/bob.md` defines none, so no entry may be invented for him. His single `⚪ Cannot statically verify` line is additionally **not queued: command shape** — it names three chained commands (`pytest`, `release-checks`, `card.py`), and a queued check must be one command with no chaining.

## Review Summary

Reviewed: 6 completed tasks
PRDs checked: 00186-add-item-grained-fast-track-lane-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only)
- Bob: ✅ Available (codex, static-only sandbox; doubt + de-slop lens)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash)

## Consolidated Findings

32 findings: 16 🟠 High, 11 🟡 Medium, 5 ⚪ Low. Every row scored `[1/4]` by
`consolidate_findings.py`.

**Consensus is under-reported by the script, and the gate says so out loud.**
Alice cites files as absolute paths with a line range (`/Users/.../SKILL.md (lines 166-171)`)
while Bob cites them as repo-relative with a single line (`skills/fast-track/SKILL.md:166`).
The paraphrase matcher requires the same file to merge, so four genuine
cross-reviewer agreements stayed split. The decision gate matches on issue text
plus file (its documented standard) and reads these four as `[2/4]`:

| Real consensus | Severity | Issue | Found By |
|----------------|----------|-------|----------|
| [2/4] | 🟠 High | Gate failure dispatches a fresh Ivan and reruns the gates instead of stopping with `stopped: gate <n>` and no reviewer dispatch | Alice, Bob |
| [2/4] | 🟠 High | The tests red-check has no green-result stop; the PRD requires `stopped: tests-green-before-implementation` | Alice, Bob |
| [2/4] | 🟠 High | `--push` pushes per clean item; the PRD requires one push after the last item's `suite: batch` run is green | Alice, Bob |
| [2/4] | 🟡 Medium | A non-`none` `changelog` field is parsed but the driver never writes or stages `CHANGELOG.md` in the item commit | Alice, Bob |

### Full script output

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 | The Gates section dispatches a fresh `autopilot:ivan` retry and reruns the gates on a red gate before stopping the item. The PRD's contract names no retry at all: "a non-zero exit stops the item with `stopped: gate <n>` and no reviewer is dispatched." This adds an unrequested, full-cost extra implementor dispatch on the exact path the PRD exists to make cheap. | skills/fast-track/SKILL.md (lines 166-171) | 4 | ALICE |
| [1/4] | 🟠 | The Tests section never instructs stopping the item when the red check comes back green. The PRD requires `stopped: tests-green-before-implementation`; that string is absent from the entire diff, so a vacuous Tess-authored test silently proceeds to Ivan. | skills/fast-track/SKILL.md (lines 121-159) | 4 | ALICE |
| [1/4] | 🟠 | `--push` is documented to push "now" at each item's clean Exit, but the PRD requires `git push` once after the last item's `suite: batch` run is green, "never per item." A multi-card invocation pushes after every clean item. | skills/fast-track/SKILL.md (lines 18-22, 423) | 4 | ALICE |
| [1/4] | 🟠 | FIX: `git commit -m` includes unrelated changes already staged outside the allowlist. Commit only the item's paths while preserving the foreign index entries. | skills/fast-track/SKILL.md:148 | 4 | BOB |
| [1/4] | 🟠 | FIX: Neither `<base-sha>` nor `<rework-base-sha>` is captured before use. Record HEAD before the item's first commit and before rework so review ranges and rollback targets are defined. | skills/fast-track/SKILL.md:182 | 4 | BOB |
| [1/4] | 🟠 | FIX: `_require_sections` accepts empty Goal, Files and Gates sections, allowing a card without an allowlist or verification commands. Reject whitespace-only sections except Tests and add rejection tests. | skills/fast-track/scripts/card.py:94 | 1 | BOB |
| [1/4] | 🟠 | FIX: Default `cost_usd: null` breaks both existing metrics renderers: their cost lists include None and `_cost_cell` calls `sum`. Support null costs in the consumer and add a producer-to-renderer integration test. | skills/fast-track/scripts/record_item.py:88 | 3 | BOB |
| [1/4] | 🟠 | FIX: Ivan's render reads `fast-track-<item>-files.txt`, but no preceding step creates it; `render_prompt.py` exits 4. Stage the absolute allowlist before rendering and include the required AGENTS.md architecture context. | skills/fast-track/SKILL.md:125 | 4 | BOB |
| [1/4] | 🟠 | FIX: Tess's PUBLIC_INTERFACES command cats every Files entry, including files the item creates. Any nonexistent entry makes rendering fail before dispatch. Read existing interfaces separately from planned target paths. | skills/fast-track/SKILL.md:84 | 4 | BOB |
| [1/4] | 🟠 | FIX: The red check occurs after committing tests and has no green-result stop. Run the first Gates command before committing; green must stop with `tests-green-before-implementation`, as specified. | skills/fast-track/SKILL.md:107 | 4 | BOB |
| [1/4] | 🟠 | FIX: An initial gate failure dispatches another Ivan and can proceed to reviewers. The PRD requires immediate `stopped: gate <n>` with unreviewed commits reported and no further dispatch. | skills/fast-track/SKILL.md:166 | 4 | BOB |
| [1/4] | 🟠 | FIX: The ordered procedure enters Rework even when the confirmed set is empty. Add an explicit empty-set transition directly to Exit, skipping both Ivan rework and delta dispatch. | skills/fast-track/SKILL.md:377 | 4 | BOB |
| [1/4] | 🟠 | FIX: Reusing the Implement render writes `-ivan.txt`, while the rework ledger call reads unwritten `-rework.txt`. Provide one consistent rework render, using confirmed checks as FAILING_TESTS and the specified rework commit. | skills/fast-track/SKILL.md:381 | 4 | BOB |
| [1/4] | 🟠 | FIX: Delta reruns the original finding lanes instead of the required single Eve dispatch. This changes dispatch counts and leaves Blake unable to inspect prior findings. Send Eve the confirmed list and rework diff once. | skills/fast-track/SKILL.md:401 | 4 | BOB |
| [1/4] | 🟠 | FIX: The driver documents one card and pushes immediately per item. Implement argument-order processing, defer the batch suite until the final item, and push once only after it passes. | skills/fast-track/SKILL.md:423 | 4 | BOB |
| [1/4] | 🟠 | FIX: The blocked exit lacks command-failure transitions. Stop if branch creation fails; if reset refuses, retain the commits and report `branch: refused (<paths>)` with `stopped: reset-refused`. | skills/fast-track/SKILL.md:429 | 4 | BOB |
| [1/4] | 🟡 | Ivan's commit in the Implement section is never told to include `CHANGELOG.md` when the card's `changelog` field is not `none`, though the PRD requires "one commit of exactly `FILES_TOUCHED` (plus `CHANGELOG.md` when `changelog` is not `none`)". | skills/fast-track/SKILL.md (lines 169-207) | 4 | ALICE |
| [1/4] | 🟡 | fast_track_prose_testutil.py is a ~692-line bespoke "reader model" built to pin SKILL.md's prose. The reused precedent task 4 was told to follow (test_dispatch_telemetry_prose.py, 374 lines) does the same job with plain substring/section matching. | skills/fast-track/scripts/fast_track_prose_testutil.py | 4 | ALICE |
| [1/4] | 🟡 | FIX: Tess receives Goal as TASK_SUBJECT and the necessarily empty Tests section as TASK_DESCRIPTION. Use item as subject and Goal plus Files as description in both documented render blocks. | skills/fast-track/SKILL.md:80 | 4 | BOB |
| [1/4] | 🟡 | FIX: Bob's prompt uses only `agents/bob.md`, omitting Eve's required Two lenses and Rubric verdicts sections. Append both and substitute PACK_FINDINGS so Bob receives the required doubt review. | skills/fast-track/SKILL.md:228 | 4 | BOB |
| [1/4] | 🟡 | FIX: A non-none changelog entry is never written or staged by the driver. Add the required CHANGELOG.md update to the item commit and pin that behavior. | skills/fast-track/SKILL.md:148 | 4 | BOB |
| [1/4] | 🟡 | FIX: Planner functions are not integrated: verify_targets and exit_action are merely cited, while plan_lanes and count_item_dispatches are unused. Add concrete calls with normalized finding inputs and consume their results. | skills/fast-track/SKILL.md:345 | 4 | BOB |
| [1/4] | 🟡 | FIX: Preconditions create only tmp. In a repository without dev/local/autopilot, both recorders silently write nothing. Create the target repository's telemetry directory before the first dispatch. | skills/fast-track/SKILL.md:40 | 4 | BOB |
| [1/4] | 🟡 | FIX: `--rework` accepts arbitrary integers despite the specified 0-or-1 contract. Add `choices=(0, 1)` and tests rejecting negative and greater-than-one values. | skills/fast-track/scripts/record_item.py:62 | 3 | BOB |
| [1/4] | 🟡 | FIX: The description contains unquoted `loop: fresh`, which is invalid inside a YAML plain scalar. Quote the description or use a folded scalar. | skills/fast-track/SKILL.md:3 | 4 | BOB |
| [1/4] | 🟡 | FIX: Three standalone roster tests duplicate cases already fully asserted by the eight-combination matrix. Remove those duplicate wrappers while retaining the matrix and explicitly required acceptance-test names. | skills/fast-track/scripts/test_fast_track_plan.py:375 | 2 | BOB |
| [1/4] | 🟡 | FIX: `_pasteable`, `_instructive` and `code_fragments` repeat the module's explanation of fenced commands in lengthy docstrings. Keep the central rationale and replace these repetitions with concise function contracts. | skills/fast-track/scripts/fast_track_prose_testutil.py:573 | 4 | BOB |
| [1/4] | ⚪ | Every `render_prompt.py` call in SKILL.md omits the `--dispatch-kind`/`--dispatch-task` flags the PRD names verbatim for Ivan, issuing a separate `record_dispatch.py start` call instead. Functionally equivalent but departs from the cited reuse pattern without being flagged as deliberate. | skills/fast-track/SKILL.md | 4 | ALICE |
| [1/4] | ⚪ | `count_item_dispatches` calls `json.loads(line)` on every non-empty split line with no try/except; a blank or truncated ledger line raises `json.JSONDecodeError` and crashes the planner rather than skipping the bad row. | skills/fast-track/scripts/fast_track_plan.py | general | BLAKE |
| [1/4] | ⚪ | `record_dispatch.append_row` writes the working ledger and the `ledger/` mirror as two separate non-atomic writes; a failure on the second leaves them out of sync. Blake notes this is pre-existing shared code outside this PRD's new files. | skills/work/scripts/record_dispatch.py | general | BLAKE |
| [1/4] | ⚪ | The exit rule and the foreign-WIP dirty-path check are documented only as SKILL.md prose; no automated test runs those git commands end to end, so a watered-down rewording could still pass the string-matching pins. | skills/fast-track/SKILL.md | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: suite success, zero skips and CLI output. (not queued: command shape — three chained commands) | N/A | general | BOB |

### Gate verification of two mechanical claims

Both were checked directly rather than taken on the reviewer's word, and both
hold. Neither contradicts the computed mechanical-facts block.

- **SKILL.md frontmatter is not valid YAML — CONFIRMED.** `yaml.safe_load` on the
  frontmatter block raises `ScannerError: mapping values are not allowed here`,
  line 3 column 102, at the `loop: fresh` inside the unquoted `description:`
  plain scalar. Bob filed it 🟡; the gate escalates it to 🟠 High, because a
  skill whose own frontmatter fails a strict YAML parse is a shipping defect in
  the artifact this PRD exists to add. (Whether the harness's own parser is
  lenient here was not established, and is not the bar.)
- **`cost_usd: null` reaches `sum()` — CONFIRMED.** `record_item.py:87` writes the
  key unconditionally (`"cost_usd": args.cost`, `None` when `--cost` is absent),
  while `cli/render_metrics.py:86,92,112,115` filter with `if "cost_usd" in row`
  — key presence, not value — so `None` enters the list and `_cost_cell`
  (`:65-66`) calls `sum(costs)` on it. Bob's 🟠 High stands as filed.

## Alice

Consensus lens, implementation-aware. 3 🟠 High, 2 🟡 Medium, 1 ⚪ Low — all
against the driver skill's prose rather than the Python modules. Her three Highs
are all PRD-contract deviations in `SKILL.md`: an unrequested Ivan retry on a red
gate, a missing green-check stop, and a per-item `--push`. She verified by `rg`
that the PRD's named outcome strings (`stopped: tests-green-before-implementation`
and friends) appear nowhere in the diff.

```
R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
```

## Blake

Blind lens, PRD-only — he never saw the diff and located the code himself. 3 ⚪
Low, and **all nineteen blind rules pass**. On the spec-compliance question the
blind lens was asked to answer, the implementation reads as complete: B1-B5
(behaviors, formats, interfaces, constraints, error handling), B6-B8 (no scope
creep), B15-B17 (phase acceptance criteria) and B18-B19 (out-of-scope) all pass.
His three findings are robustness observations, one of which he flags himself as
pre-existing shared code outside this PRD.

```
B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass
```

## Bob

Doubt + de-slop lens, codex, static-only sandbox. By far the heaviest reporter:
13 🟠 High, 9 🟡 Medium, 1 ⚪ Low. His Highs concentrate on `SKILL.md` as an
executable procedure — render inputs that would fail at dispatch (a file no step
creates, a `cat` over paths the item has not created yet, a rework render whose
filename does not match the ledger call it is paired with), missing base-SHA
capture, missing failure transitions on the blocked exit, and control flow that
enters rework with an empty confirmed set. Two of his findings were independently
confirmed by the gate above.

He emitted no FIX/VERIFY/KNOWN section structure (his persona defines none), so
no verification-check queue was written from his output.

```
R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Frontend & design specialist, generalist here (this change has no UI surface).
Backend `copilot`, model `gemini-3.8-flash`, exit 0, non-empty output. He ran the
suite and `dev/bin/release-checks` himself, read every new module and reference,
checked function and file length limits with his own `ast` pass, searched for
TODO/FIXME/pdb markers, executed the `card.py` CLI against the `valid.md` fixture,
and re-ran task 6's acceptance commands. He reports no issues and passes all
twelve rules.

```
[CARL] ✅ No issues found
```

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

## Follow-up Tasks Created

Ten `[D1]` tasks at tier `opus` (classifier default `sonnet` raised by the PRD's
`default_model: opus` floor), covering 24 of the 32 findings. The scope alarm
(>10 tasks) does not fire at exactly ten.

1. Driver stop rules: tests-green and red-gate (L) - 🟠 High - 4 findings
2. Multi-card processing, batch suite and a single push (M) - 🟠 High - 2 findings
3. Base SHA capture and exit-rule failure transitions (M) - 🟠 High - 2 findings
4. Prompt render inputs that fail at dispatch (L) - 🟠 High - 3 findings
5. Commit scope and the changelog field (M) - 🟠 High - 3 findings
6. Verify/rework/delta control flow (M) - 🟠 High - 2 findings
7. card.py rejects empty required sections (S) - 🟠 High - 1 finding
8. record_item.py contract: null cost and --rework bounds (S) - 🟠 High - 2 findings
9. SKILL.md frontmatter is not valid YAML (S) - 🟠 High - 1 finding
10. Driver wiring gaps: Tess inputs, Bob's prompt, planner calls, telemetry dir (M) - 🟡 Medium - 4 findings

### Carried, not tasked this cycle

Eight Medium/Low findings are recorded but not tasked, so the cycle stays inside
the ten-task bound. None blocks convergence (Medium and Low never do), and the
tail sweep is the mechanism that closes them at convergence:

- 🟡 `fast_track_prose_testutil.py` is a 692-line bespoke reader model where the cited precedent uses plain substring matching (Alice)
- 🟡 Three standalone roster tests duplicate the eight-combination matrix (Bob)
- 🟡 `_pasteable`/`_instructive`/`code_fragments` repeat the module rationale in their docstrings (Bob)
- ⚪ `render_prompt.py` calls omit `--dispatch-kind`/`--dispatch-task` (Alice)
- ⚪ `count_item_dispatches` has no `try`/`except` around `json.loads` (Blake)
- ⚪ `record_dispatch.append_row`'s two non-atomic writes — Blake's own note says pre-existing, outside this PRD (Blake)
- ⚪ The exit rule has no end-to-end git test, only prose pins (Blake)
- ⚪ Bob's un-queued "cannot statically verify" line (Bob)

Verdict: 32 findings

Tests: 350 passed, 0 failed, 0 skipped (reused from last-verification.json at b909eb0a095134d0f722e7e6e3fea82cab9801ea)
