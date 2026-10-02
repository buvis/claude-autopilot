---
catchup: skip
design: skip
---

# Trim rework and review ceremony

Source: `~/.claude/dev/local/discovery/00148-autopilot-fast-track-learnings.md` § 4 (option c), § 6 and § 8 (engram). The other sections are done (§ 1, § 9a-b, § 9d), queued in PRD 00141 (§ 3, § 5, § 9c), recorded on PRD 00110 (§ 2), or belong to `~/.claude` (§ 7). Numbers below come from that run; none is a guess unless marked `(guess)`.

## Problem

Three small costs recur on every review-rework cycle. (1) Rework tasks below the step-5.6 skip threshold still pay the full per-task ceremony: PRD 00136 task 4 (a -25 net-line prose trim in test files) took ~15 min and ~100K subagent tokens (Ivan 80K, Pat ~20K); task 5 (two code lines, four doc lines) took ~20 min. Three scratch files, a render, a watchdog, a review render and a sonnet runner dominate below ~30 net lines, for edits the orchestrator could make in two `Edit` calls. (2) During Tess's task-5 dispatch `test_enforce_write_scope.py` acquired a whole-file formatter reflow (58 hunks: trailing commas, line splits) nobody asked for; the trigger is unknown (loupe carries autofixers, but Ivan's edits to the same file 20 minutes earlier were clean). The commit had to be hunk-scoped by hand with `git apply --cached`; `/work` step 5 has no way to notice a reflow, so an unattended run sweeps it into the task commit and cycle 2 re-reviews 58 formatting hunks. (3) In a bare-repo home `engram pack` fails every cycle ("must run inside a git worktree"); `review-work-completion` step 3 already says to expect that and move on, yet still runs the command, so every review file carries a red line and every cycle spends the attempt.

## Solution

Three deterministic additions, each recorded in the attempt or review file so nothing is silent. (1) A **micro lane** in rework mode: when a rework task's `### Findings (verbatim)` block is small (rule below) and its files are clean, the orchestrator implements it directly with the `Edit` tool, Tess/Devon/red-check are skipped, Pat's step-5.7 review and step-5.5 verification are kept, and the attempt is stamped `implementor: "orchestrator"`. A post-edit ceiling (the step-5.6 formula) reverts and falls through to the normal Ivan dispatch when the change turns out larger than expected, stamping `micro_lane: "overrun"`. (2) A **reflow tripwire** script at `/work` step 5: hunk count per file in `FILES_TOUCHED`; over the threshold, the file is still committed (hunk-scoping stays manual, learnings option a) but the attempt gets `reflow: "<path>:<hunks>"` and the phase report names it, so the sweep is visible and the trigger can be found from data. (3) `review-work-completion` step 3 runs `git rev-parse --show-toplevel` first and skips the `engram pack` attempt when it fails, writing `pack: skipped (no git worktree)` instead of a failure line.

## Requirements

### Must have
- `skills/work/scripts/work_routing.py` gains `micro_lane_eligible(severities, files, in_rework) -> bool`, pure: `True` only when `in_rework` is true, `len(severities) <= 2`, the distinct `files` (paths before any `:line` suffix) number `<= 2`, and no severity is `CRITICAL`. `(guess)` - the 2/2 bound is a proxy for "expected diff under the step-5.6 threshold", which cannot be measured before editing; the post-edit ceiling below is the real guard.
- `skills/work/references/rework-mode.md` gains `## Micro lane`: the orchestrator extracts severities and file paths from the task's `### Findings (verbatim)` block, calls `micro_lane_eligible`, and additionally requires every named file to be clean in `git status --porcelain` at claim time (so the revert below cannot destroy foreign work). Eligible: steps 2.7, 2.8, 2.85, 2.9 and 2.95 are skipped; the orchestrator edits with the `Edit` tool only (no subagent, no shell edits); before committing, measure `git diff --shortstat HEAD -- <files>` and the touched-file count with the step-5.6 formula (`net_lines = insertions - deletions`; `file_count`): `net_lines >= 30` OR `file_count > 2` is an **overrun** - `git checkout -- <files>`, stamp `micro_lane: "overrun"` on the attempt, and continue at step 2.7 as a normal task. Otherwise step 5 commits the edited files, step 5.5 runs the task's `Verify:` command (or the project's narrowest test command covering the touched modules when `Verify:` is absent), step 5.6 records `self_deslop: "skipped:trivial"` without dispatching, and step 5.7 runs Pat unchanged with `BASE_SHA` = the parent of the lane commit; the step-5.7 retry rows edit through the orchestrator instead of re-rendering Ivan. The attempt record carries `implementor: "orchestrator"`, `red_check: "n/a:micro-lane"`, `review_cycle` as rework mode already sets it.
- `skills/work/SKILL.md` step 3 gains at most two lines pointing at `references/rework-mode.md` § Micro lane, placed before the routing table; the body stays under the 500-line ceiling (`test_work_skill_body_stays_under_the_500_line_ceiling`, today 487 lines; PRD 00141 claims up to five more).
- `skills/work/scripts/check_reflow.py <path>...` (stdlib only): for each path runs `git diff -U0 HEAD -- <path>` (forwarding optional `--git-dir`/`--work-tree` flags for a bare-repo home), counts lines starting with `@@`, prints `<path>\t<hunks>` for every path at or above `--threshold` (default 20 `(guess)` - the observed reflow was 58 hunks, a targeted edit is under 10), exits 0 when nothing is flagged, 1 when something is, 2 when git fails (message on stderr). Never modifies files.
- `skills/work/SKILL.md` step 5 gains at most two lines: after building the stage list, run `check_reflow.py` over it; exit 1 -> stamp `reflow: "<path>:<hunks>"` (`;`-joined for several) on the attempt and name the files in the phase report; exit 2 -> `reflow: "failed:<stderr>"`; exit 0 -> field absent. Staging and the commit proceed unchanged in every branch. The procedure detail lives in `references/subagent-dispatch.md` under a new `## Reflow tripwire` heading.
- `skills/work/references/attempt-logging.md` and `skills/run-autopilot/references/state-schema.md` (`tasks[].attempts` row) add `"orchestrator"` to `implementor`, the optional fields `micro_lane: "overrun"` and `reflow: string`, and the `red_check` value `"n/a:micro-lane"` (PRD 00141 adds its own `n/a:` siblings; both lists coexist).
- `skills/review-work-completion/SKILL.md` step 3, the bare-repo paragraph: before the `engram pack` command run `git rev-parse --show-toplevel` from the project root with no extra flags (the pack resolves `repo_root` the same way); non-zero exit -> do not run `engram pack`, substitute `(no pack available this cycle)` for `{PACK_FILE}`/`{PACK_FINDINGS}`, and write `pack: skipped (no git worktree)` in the review file. Zero exit -> today's flow, including the one retry.
- Tests, fail-first per `rules/testing.md`: `test_work_routing.py` covers `micro_lane_eligible` (rework off -> false; three findings -> false; three files -> false; a CRITICAL -> false; two MEDIUMs in one file -> true). New `test_check_reflow.py` builds a temp git repo: a one-hunk edit exits 0 and prints nothing; a file whose every other line changed (30 hunks) exits 1 and prints `<path>\t30`; a path outside any repo exits 2. `test_dispatch_prose.py` pins: `rework-mode.md` names `implementor: "orchestrator"`, `micro_lane: "overrun"` and `git checkout -- `; SKILL.md step 3 names `rework-mode.md` and `Micro lane`; step 5 names `check_reflow.py` and `reflow:`; `attempt-logging.md` lists the three new values. `skills/review-work-completion/scripts/test_agent_registry.py` pins that step 3 names `git rev-parse --show-toplevel` before `engram pack` and the literal `pack: skipped (no git worktree)`.
- `CHANGELOG.md` `[Unreleased]` gains one `**work**` and one `**review-work-completion**` line under Added (feat commits, `rules/changelog.md`).

### Nice to have
- `tracon/panels.py` already shows any non-`claude` implementor next to the task; no change unless the `orchestrator` label overflows the lane width.

## Implementation

### Module: micro-lane
- **Location**: `skills/work/scripts/work_routing.py`, `skills/work/scripts/test_work_routing.py`, `skills/work/references/rework-mode.md`, `skills/work/SKILL.md` (step 3, two lines)
- **Responsibility**: the eligibility predicate, the lane procedure with its overrun revert, and the step-3 pointer.
- **Exports**: `micro_lane_eligible(severities, files, in_rework)`

### Module: reflow-tripwire
- **Location**: `skills/work/scripts/check_reflow.py`, `skills/work/scripts/test_check_reflow.py`, `skills/work/references/subagent-dispatch.md`, `skills/work/SKILL.md` (step 5, two lines)
- **Responsibility**: hunk-count detection over the stage list and the `reflow:` stamp.
- **Exports**: CLI `check_reflow.py [--threshold N] [--git-dir D --work-tree W] <path>...`

### Module: attempt-schema
- **Location**: `skills/work/references/attempt-logging.md`, `skills/run-autopilot/references/state-schema.md`, `skills/work/scripts/test_dispatch_prose.py`
- **Responsibility**: document the new implementor value and fields; prose pins for all `/work` changes.
- **Exports**: none (prose)

### Module: engram-skip
- **Location**: `skills/review-work-completion/SKILL.md` (step 3), `skills/review-work-completion/scripts/test_agent_registry.py`
- **Responsibility**: the worktree pre-check and the `pack: skipped` line.
- **Exports**: none (prose)

### Dependencies
- reflow-tripwire: No dependencies (foundation)
- engram-skip: No dependencies (foundation)
- micro-lane: No dependencies (foundation)
- attempt-schema: Depends on [micro-lane, reflow-tripwire] (documents their stamps)

## Tasks

### Phase 0: Foundation
- [ ] `check_reflow.py` + `test_check_reflow.py` - `uv run --with pytest pytest skills/work/scripts/test_check_reflow.py -q` green; the three exit codes each have a test; `python3 skills/work/scripts/check_reflow.py --threshold 1 skills/work/SKILL.md` on a clean tree exits 0 with no output.
- [ ] `micro_lane_eligible` in `work_routing.py` + the five `test_work_routing.py` cases - `uv run --with pytest pytest skills/work/scripts/test_work_routing.py -q` green; `route()` byte-identical to HEAD.
- [ ] `review-work-completion` step 3 worktree pre-check + `test_agent_registry.py` pin - `rg -n "git rev-parse --show-toplevel" skills/review-work-completion/SKILL.md` hits inside step 3 before the `engram pack` block; `rg -n "pack: skipped \(no git worktree\)"` hits; `uv run --with pytest pytest skills/review-work-completion/scripts/test_agent_registry.py -q` green.

### Phase 1: Core
- [ ] `rework-mode.md` § Micro lane, the SKILL.md step-3 pointer, the SKILL.md step-5 tripwire lines, `subagent-dispatch.md` § Reflow tripwire (depends on: Phase 0) - `rg -n "Micro lane" skills/work/SKILL.md skills/work/references/rework-mode.md` hits both; `rg -n "check_reflow.py" skills/work/SKILL.md skills/work/references/subagent-dispatch.md` hits both; `wc -l skills/work/SKILL.md` <= 491.
- [ ] `attempt-logging.md` + `state-schema.md` values, `test_dispatch_prose.py` pins, CHANGELOG lines (depends on: Phase 1 task 1) - `rg -n '"orchestrator"' skills/work/references/attempt-logging.md skills/run-autopilot/references/state-schema.md` hits both; `rg -n "micro_lane|reflow" skills/work/references/attempt-logging.md` hits; `uv run --with pytest pytest skills/work/scripts/test_dispatch_prose.py -q` green; `rg -n "^- \*\*work\*\*" CHANGELOG.md` hits under `[Unreleased]`.

## Success Criteria

- `uv run --with pytest --with rich --with textual pytest skills/work/scripts skills/review-work-completion/scripts skills/run-autopilot -q` green.
- `skills/work/SKILL.md` grew by at most four lines; `route()` in `work_routing.py` unchanged.
- Post-release signals (the batch runs the installed plugin cache, not this tree): the next rework cycle with a two-finding task shows an attempt with `implementor: "orchestrator"` and a Pat verdict in the review file, and its wall-clock in the batch report is under 5 min; the next review in a bare-repo home shows `pack: skipped (no git worktree)` with no engram failure line; any attempt stamped `reflow:` names a file whose diff was hunk-inspected in the phase report.
