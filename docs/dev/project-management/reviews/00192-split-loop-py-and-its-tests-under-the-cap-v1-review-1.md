---
prd: dev/local/prds/wip/00192-split-loop-py-and-its-tests-under-the-cap-v1.md
review: 1
date: 2026-09-15
head_sha: ccdc9650dc48e908aa99949bc6e49ce16b319de3
codex_thread_id: 01a0a240-3c59-7410-bdd5-a707818d10f2
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00192-split-loop-py-and-its-tests-under-the-cap-v1

Diff range: `54b7706cf1887034a33285253f5e87e489da8eeb..ccdc9650dc48e908aa99949bc6e49ce16b319de3`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv", the same deterministic error every cycle of batch 202609061630 has recorded, so no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. Degraded, not invalid.

scope note: cycle 1, full review of the PRD's whole work range (9 commits, 11 files, +2285/-2007). `gather-context.sh` was run with `--since 54b7706…` (`state.work_start_sha`) because its default base is `master` and the batch works on `master`, so the bare form yields an empty diff; the context file's scope label was corrected by hand to say "full review". The design doc (`design: run`) was appended to the PRD summary under `## Design Doc` for the implementation-aware reviewers. Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory — `readlink` exits 1 — and the root has no dot prefix). The computed blocks were appended to the context file: mechanical facts (every function in all 11 changed files counted; none over 50), tautological shapes (93 test functions in 6 files, none flagged), fail-first replay (0 touched tests ran: all 6 test files fail to collect at base because the seam modules they import do not exist there — expected for a module split; no `[MECH]` line), the recorded verification at HEAD.

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a0a240-…` captured for the next cycle's `--resume-thread`). One PreToolUse gateguard block on his first shell command (`[Fact-Forcing Gate]`), after which he recovered and read everything. No lack-of-input shape, all twelve `R` lines, five `D` lines and the FIX/VERIFY/KNOWN buckets present, so no retry was spent. Bob's `File:` value carries a `:line` suffix and is kept as he wrote it.

carl note: gemini-run backend=copilot model=gemini-3.8-flash, exit 0, non-empty output. Independent this cycle: his transcript shows no read of any other reviewer's output file (Bob finished after him). He ran the full CLI suite, `release-checks` twice (once with the host dispatch markers unset), `bodies.py` over the four implementation files against `bodies-trim.txt` (empty diff), the golden hashes, the import-graph checks and the fixture-binding count himself.

verification queue: none written this cycle. Bob emitted one FIX item, `VERIFY: (none)`, `KNOWN: (none)`. Eve did not run (`doubt_reviewer: codex`, no codex-implemented task in `state.tasks`).

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00192-split-loop-py-and-its-tests-under-the-cap-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; `wc -l` on the ten split files, import smoke, `git log` of the 9 commits, an independent `check_style_limits.py --diff` run (exit 0), the narrow `test_loop*` + `test_loop_review_once` suite (96 passed), byte-read of `loop.py`'s import block / `__all__` / `class Loop(GatesMixin, DecisionMixin, ActMixin)` against the design's literal contracts, `_fingerprint_bound` call site, `__main__.py --help`; 0 findings; all twelve R rules pass)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; located the design doc and all eleven files, `wc -l` ten files under 800, full CLI suite 1092/1092 at HEAD, goldens 10 OK, `release-checks` clean, import smoke, `__all__` = the design's 13 names, `git diff --stat` outside `cli/` and `dev/local` empty, seam import graph acyclic, plus a detached worktree of commit 5235090; 1 🟡; B15 fails on it, the other eighteen B rules pass)
- Bob: ✅ Available (codex, exit 0, static analysis; doubt + de-slop lens; 1 ⚪; all twelve R rules pass; D1-D5 pass)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0; full suite, `release-checks` x2, `bodies.py` vs `bodies-trim.txt`, goldens, import graph, bindings; 0 findings; all twelve R rules pass)

## Consolidated Findings

2 findings from `consolidate_findings.py` over four reviewer outputs; no paraphrase merges needed (the two findings name different files). No `[MECH]` rows to absorb, no carry-forward (cycle 1). No 🔴 Critical, no 🟠 High; 1 🟡 Medium, 1 ⚪ Low.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 Medium | Intermediate commit 5235090 ("test(run-autopilot-cli): pin the cli.loop compat surface (00192 seam 4)") adds test_loop_exports.py alone, before loop_act.py exists and before __all__ is added to loop.py; `from cli import loop, loop_act, loop_decision, loop_gates` fails with ImportError, so pytest collection errors out and the ENTIRE CLI suite fails at that commit (verified independently in an isolated `git worktree add --detach` checkout of 5235090: `ImportError: cannot import name 'loop_act' from 'cli'`, "1 error during collection"). This directly violates the PRD's Phase 1 task acceptance criterion ("after each commit, [the CLI suite] passes") and the Success Metric ("After every seam commit, the CLI suite passes"). The very next commit (3712430, ~10 min later) does the actual loop_act.py move and fixes it, and HEAD is fully green, but the per-commit invariant the PRD explicitly requires (git-bisectable, always-green history through a refactor of the loop core) was broken for one real commit in the merged history. **(deferred to batch end, reason below)** | skills/run-autopilot/cli/test_loop_exports.py (commit 5235090) | Phase 1 (Moves) | Blake |
| [1/4] | ⚪ Low | Updated docstring incorrectly says `loop_testutil.py` exceeds 1,300 lines; remove the obsolete size/case-count parenthetical. | skills/run-autopilot/cli/test_loop_review_once.py:8 | 3 | Bob |

### Decision gate (Phase 5)

Cycle 1 of cap 3. **No unresolved 🔴/🟠 → converged**, pending the constraint gate (`autopilot gate --require-codex-guard --assert-constraint-met`, run after this file is saved). The Medium/Low tail is swept, not dropped: one `[D1]` task (1 finding, no split) dispatched through `/autopilot:work` in rework mode, then the PRD finalizes without another review cycle. Every decision is in `state.autonomous_decisions` or `state.deferred_decisions`; the deferral is in `00192-split-loop-py-and-its-tests-under-the-cap-v1-ledger.json` (`settled-deferral`) and mirrored into the batch deferred JSON (`autopilot defer`). No settled deferrals from a prior cycle (cycle 1), no scope alarm (1 follow-up task), no recurring issue, no verification queue, no discard.

- **Deferred to batch end (1, Blake's 🟡, `deferred_decisions` type `requirements-ambiguity` + ledger + batch deferred JSON):** confirmed by the orchestrator (`git ls-tree --name-only 5235090` lists `test_loop_exports.py` and not `loop_act.py`), so the suite cannot collect at that commit. Not fixable forward: HEAD and every seam implementation commit (e7c1125, ea3260c, 3e15de5, a437237, 3712430) are green, and the red commit is the `work` skill's tests-first pipeline landing Tess's red test (`5235090`) before Ivan's implementation (`3712430`) — the standard commit shape of every tests-first task in this batch (`9c6753a → 9a933a0`, `f298ed3 → 278e7d3`, `44542d6 → 54b7706`). The only remedy is a rewrite of unpushed `master` history (fixup 5235090 into 3712430), which an unattended session must not do on a checkout other sessions commit into. The human decides at batch end: squash, or read the PRD's per-commit criterion as "per seam implementation commit". Upstream question for the pack: should the `work` skill's tests-first path commit test and implementation together when a PRD requires an always-green, bisectable history.
- **Swept (1, Bob's ⚪ → task `[D1]`):** confirmed by reading `test_loop_review_once.py:8-9` — the sentence now names `cli/loop_testutil.py` but keeps "(that file is already past 1300 lines; these nine cases would push it further)", true of `test_loop.py` at 54b7706 and false for the 195-line `loop_testutil.py`. Fix: drop the parenthetical (Bob's suggested wording: "Shared fixtures come from cli/loop_testutil.py."). Docs-only, no behavior change.

Not findings, recorded for visibility: Alice notes `test_loop_exports.py` deviates from the design's "verbatim" body (`Loop.__bases__` tuple equality plus two `.__module__` asserts instead of three `issubclass` lines) — a deliberate strengthening already recorded in `state.autonomous_decisions` at task 6 (the Devon forwarding-proxy exploit); every counted inventory is unaffected.

## Follow-up Tasks Created

No step-7 tasks: this cycle converges, so the Medium/Low tail is the decision gate's Tail sweep, which creates exactly ONE `[D1]` task carrying the swept finding verbatim.

1. Task 8 — `[D1]` Sweep cycle-1 findings: drop the stale size parenthetical from the test_loop_review_once.py docstring (S) - ⚪ Low - 1 finding; tier `opus` (classifier would say sonnet; the PRD's `default_model: opus` floor raises it); `state.rework_task_ids = ["8"]`.

### Tail sweep result (same session, after `/autopilot:work`)

Task 8 completed via the micro lane (`references/rework-mode.md` § Micro lane: 1 Low finding, 1 file, clean at claim): the orchestrator made the docstring edit itself, commit a68ec83 (`docs(run-autopilot-cli): drop the stale size parenthetical from the test_loop_review_once docstring (00192 sweep)`, 1 insertion, 2 deletions, `check_reflow.py` exit 0). Step 5.5 ran the task's `Verify:` commands (`rg "1300 lines"` no match; the replacement sentence present once at line 8; `test_loop_review_once.py` 10 passed). Style gate exit 0, split hygiene exit 0, `self_deslop: skipped:trivial`. Pat (sonnet-run, no tools, session B337420E): `CLOSURE | resolved` on the one finding, `NO FINDINGS`. Step 7 at a68ec83: full CLI suite `1092 passed, 6 warnings, 657 subtests passed`, `bash dev/bin/release-checks` exit 0, no queued checks; recorded in `last-verification.json`. Tree clean. No verify-escapes (no queue) and no sweep-escapes (Pat raised no C/H). Converged at cycle 1; the PRD finalizes without another review cycle.

## Alice

Consensus lens, Claude subagent (sonnet), first dispatch, no retry. Verified independently: sizes, import smoke, the 9-commit log, `check_style_limits.py --diff` exit 0, the narrow loop suites (96 passed), byte-reads of the import block / `__all__` / `Loop` bases against the design, `_fingerprint_bound` wiring, `__main__.py --help`, no TODO/skip/xfail/secrets, no CHANGELOG diff (pure refactor). 0 findings.

```
[ALICE] ✅ No issues found
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

## Blake

Blind lens, Claude subagent (sonnet), PRD + B-rubric only, first dispatch, no retry. Found the design doc and every produced file himself; re-ran the sizes, the full suite (1092/1092), goldens (10 OK), `release-checks`, import smoke, the `__all__` surface, the outside-scope `git diff --stat` (empty) and the seam import graph; checked out 5235090 in a detached worktree to reproduce the collection error. 1 🟡; B15 fails on it.

```
[BLAKE] 🟡 Intermediate commit 5235090 ("test(run-autopilot-cli): pin the cli.loop compat surface (00192 seam 4)") adds test_loop_exports.py alone, before loop_act.py exists and before __all__ is added to loop.py; `from cli import loop, loop_act, loop_decision, loop_gates` fails with ImportError, so pytest collection errors out and the ENTIRE CLI suite fails at that commit (verified independently in an isolated `git worktree add --detach` checkout of 5235090: `ImportError: cannot import name 'loop_act' from 'cli'`, "1 error during collection"). This directly violates the PRD's Phase 1 task acceptance criterion ("after each commit, [the CLI suite] passes") and the Success Metric ("After every seam commit, the CLI suite passes"). The very next commit (3712430, ~10 min later) does the actual loop_act.py move and fixes it, and HEAD is fully green, but the per-commit invariant the PRD explicitly requires (git-bisectable, always-green history through a refactor of the loop core) was broken for one real commit in the merged history. | File: skills/run-autopilot/cli/test_loop_exports.py (commit 5235090) | Task: Phase 1 (Moves)

[BLAKE] ✅ Everything else checked out. Read the design doc at dev/local/designs/00192-split-loop-py-and-its-tests-under-the-cap-v1-design.md (the PRD's required Phase 1.5 reviewed map) and every produced file (loop.py, loop_decision.py, loop_gates.py, loop_act.py, loop_testutil.py, test_loop.py, test_loop_decision.py, test_loop_gates.py, test_loop_act.py, test_loop_exports.py, test_loop_review_once.py). Independently verified (not just trusting the implementer's self-report in dev/local/tmp/00192-baseline/final-check.txt): `wc -l` on all ten split files is under 800 (loop.py 515, loop_decision.py 356, loop_gates.py 303, loop_act.py 363, loop_testutil.py 195, test_loop.py 647, test_loop_decision.py 377, test_loop_gates.py 418, test_loop_act.py 189, test_loop_exports.py 49); `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot/cli` at HEAD (ccdc965) passes 1092/1092; `shasum -a 256 -c dev/local/tmp/00192-baseline/golden.sha256` reports all 10 golden files OK (byte-identical); `bash dev/bin/release-checks` exits clean across every section; the import smoke test (`import cli.loop, cli.loop_decision, cli.loop_gates, cli.loop_act`) succeeds and `cli.loop.__all__` matches the design's exact 13-name compat surface. `git diff --stat 54b7706..HEAD` outside `skills/run-autopilot/cli` and `dev/local` is empty — confirms the PRD's Non-Goals (routing.py, records.py, state.py, __main__.py, test_state.py untouched; no behavior/verb/flag changes). No seam module imports cli.loop or a higher seam (loop_decision imports nothing from the seams; loop_gates and loop_act import only loop_decision; loop.py imports all three) — matches the PRD's "lower-level seams do not import loop.py" requirement. The Loop class correctly inherits GatesMixin, DecisionMixin, ActMixin and every mixin's methods, docstrings and monkeypatch targets match the reviewed design. No new external dependencies, no new CLI flags/verbs, no auth/data-migration/destructive-operation concerns apply to this PRD (pure internal module split).

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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass
```

## Bob

Doubt + de-slop lens, codex (static-only sandbox), first dispatch, no retry. 1 ⚪, one FIX item, no VERIFY, no KNOWN. All twelve R rules pass; D1-D5 pass. The orchestrator confirmed the finding by reading the cited lines.

```
[BOB] ⚪ Updated docstring incorrectly says `loop_testutil.py` exceeds 1,300 lines; remove the obsolete size/case-count parenthetical. | File: skills/run-autopilot/cli/test_loop_review_once.py:8 | Task: 3

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

FIX:

- Stale harness description — skills/run-autopilot/cli/test_loop_review_once.py:8 — Replace the paragraph with "Shared fixtures come from cli/loop_testutil.py."

VERIFY:

- (none)

KNOWN:

- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Consensus lens, gemini-run backend=copilot model=gemini-3.8-flash, exit 0, no retry. Read the whole context file (with the design doc), `final-check.txt`, `bodies.py`, `test_loop_exports.py`, the heads of `loop_gates.py` / `loop_act.py` / `loop.py`; ran the full CLI suite, `release-checks` (also with the inherited dispatch markers unset), `bodies.py` vs `bodies-trim.txt` (no diff), the golden hashes, both import-graph greps, the fixture-binding count, and the skip/xfail, TODO and secret greps. No frontend surface, reviewed as a generalist. 0 findings.

```
[CARL] ✅ No issues found

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

## Mechanical checks

- Mechanical facts: every function in all 11 changed files counted from `ast` (block appended to the context file); the largest are `test_review_exit_to_done_writes_the_convergence_row` 49 and `test_convergence_row_fields_come_from_state_and_review_files` 49 (both pre-existing, moved verbatim); every implementation function is under 50 (`_act_branch` 46, `_append_metrics` 46, `Loop.__init__` 43, `_run_once` 43).
- Tautological shapes: none (93 test functions in 6 files checked).
- Fail-first replay: `0 touched test(s) ran, 0 failed against base, 0 passed; 6 test file(s) could not be collected at base` — every touched test file imports `cli.loop_testutil` / `cli.loop_decision` / `cli.loop_gates` / `cli.loop_act`, none of which exists at 54b7706, so the replay cannot say anything about this PRD; no `[MECH]` line was produced and none was absorbed.
- Orchestrator checks (before dispatch): ten split files 515/356/303/363/195/647/377/418/189/49 lines (all < 800); `shasum -a 256 -c golden.sha256` 10 OK; check 9 import-graph greps print nothing; task 7's `final-check.txt` records checks 1/2/2b/3/5/6 exit 0 at ccdc965 (1092 ids = baseline 1091 + 1, 267 asserts, 123 test rows, 60 impl rows vs `bodies-trim.txt`, 4 bindings).

Verdict: 2 findings

Tests: 1092 passed, 0 failed, 0 skipped (reused from last-verification.json at ccdc9650dc48e908aa99949bc6e49ce16b319de3)
