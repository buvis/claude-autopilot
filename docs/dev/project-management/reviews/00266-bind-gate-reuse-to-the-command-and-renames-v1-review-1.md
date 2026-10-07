---
head_sha: e87f36aa84edfae243ce1326065af718c6fa9b77
reviewers: alice, blake, eve, bob, carl
---

# Fast-track lane review: 00266-bind-gate-reuse-to-the-command-and-renames-v1

One card, run through the full fast-track roster. Per-card detail, the
consolidated table, the adversarial verdicts and the gate history live in
`docs/dev/tmp/00266-bind-gate-reuse-to-the-command-and-renames-v1-c1-fast-track-review.md`.

## Alice

**00266-bind-gate-reuse-to-the-command-and-renames-v1-c1**

Ran as the `autopilot:alice` subagent, not the `review-fanout` workflow: the
workflow file is on disk but its `personas` argument needs seven persona
bodies passed inline as workflow args, which cannot be assembled without
inlining them into the driver's context. The documented fallback was used and
the `fast-track:fanout` ledger row closed as `error` with that reason.

9 findings, 2 of them 🟠. Both 🟠 went to adversarial verification; one was
refuted and one confirmed.

- 🟠 PRD #16's `--relative -- .` / `-uall` scoping not implemented as written;
  `_ancestor_and_clean` prepends `rev-parse --show-prefix` instead, leaving
  `git log` and `git status` scoped to the whole toplevel. **REFUTED** by
  `autopilot:victor`: the root defect is fixed, the deviation only makes the
  record stale more often (fails safe, never wrongly reused), and
  `git status --porcelain` has no `--relative` flag, so the spec could not be
  followed literally. The doubt lens independently filed the same thing as
  KNOWN. Mechanism left as implemented.
- 🟠 `reuse_verdict` and `stage` each 54 lines, over the 50-line limit.
  **CONFIRMED**: measured with `ast` against the base blob they were 49 and 48
  lines, so this diff pushed both over. Fixed in rework by extracting
  `_record_shape_ok` and `_tmp_escape_refusal`.
- 🟡 `gate_command` optional, so a caller that omits it loses the #6
  protection. Fixed in rework (now a required `str`).
- 🟡 `status` missing `-uall`. Folded into the refuted #16 row; left as is.
- 🟡 The symlink regression test hedges either-or. Fixed in rework.
- 🟡 `docs/dev/tmp` containment check runs after `mkdir`. Fixed in rework.
- 🟡 `test_review_stage.py` over the 800-line limit. Fixed in rework by
  splitting out `test_review_stage_paths.py`.
- ⚪ `reuse_verdict` docstring drift. Survives, non-blocking.
- ⚪ Could not run the shell harness (warden blocked the call); pytest 67 passed.

## Blake

**00266-bind-gate-reuse-to-the-command-and-renames-v1-c1**

Knew only the card, located the code himself. Confirmed all seven PRD fixes
work, by reading and by running: pytest 87 passed, and the shell harness 11/11
PASS including all three new cases. 5 findings, none above 🟡.

- 🟡 `stage()` creates `docs/dev/tmp` before checking containment, so a
  symlinked `docs/dev` leaks a `tmp` outside the repo. Fixed in rework.
- 🟡 `gate_command` is fail-open for a caller that forgets it. Fixed in rework.
- ⚪ #16 not done as the spec worded it; fails safe. Left as is (refuted).
- ⚪ The code compares every recorded command, not just `commands[0]`, and the
  sha regex accepted 64 hex as well as 40. Stricter than spec on the first,
  narrowed to 40-hex in rework on the second.
- ⚪ `_stage_inputs_from_state` lives in `cli/__main__.py`, which the card's
  Files list omitted. The driver extended the allowlist to match the PRD's own
  wording. Two pre-existing unguarded edges noted: a non-string truthy
  `design_doc` raises `TypeError`, and `prd: "."` resolves to `wip` itself.

Rubric: B14 fail, the other 18 pass.

## Eve

**00266-bind-gate-reuse-to-the-command-and-renames-v1-c1**

Cycle-1 doubt + de-slop pass: 9 findings = 6 FIX + 1 VERIFY + 2 KNOWN, D1-D5
all pass. Proved fail-at-base for all 8 new pytest cases against a scratch
copy at the base commit, and probed the #23 gap directly: `stage()` with
`docs/dev` symlinked outside returned the refusal dict *and* left
`<outside>/tmp` created. Also caught an uncommitted loupe reflow that had
landed on three in-scope files after they were committed; the driver reverted
it per the project rule rather than committing it.

Delta pass over the rework commit (`0b07299..HEAD`): all seven prior findings
confirmed resolved in code, with the #23 fix proven fail-first (the new test
dropped into a tree extracted at the base commit failed with exactly the leak
it pins, then passed at HEAD). 3 residual FIX, 0 VERIFY, 3 KNOWN; D1-D5 all
pass. Nothing above 🟡 survives.

Surviving, non-blocking: the `reuse_verdict` docstring no longer matches the
code this PRD shipped (and the repo pins that docstring with a test); the
`stage()` docstring omits the new tmp-escape refusal; `stage()` sits at exactly
50 lines rather than under. Out of scope by the card: no CHANGELOG entry for a
user-visible fix, the 40-hex regex excluding SHA-256 repos, and the #23 guard
not covering an in-repo symlink target.

## Bob

**00266-bind-gate-reuse-to-the-command-and-renames-v1-c1**

Static-only sandbox (codex, gpt-6-astra). 8 findings, all 🟡: `gate_command`
optional; the prefix fix leaving log/status worktree-scoped; `status` omitting
`-uall`; the sha regex accepting 64 chars; `mkdir` before the containment
check; the staging refusal returning exit 1 where it read the PRD as requiring
2; and `stage`/`reuse_verdict` over 50 lines with the test file over 800. Six
of the eight were fixed in rework; the two #16-scoping rows were left as is on
the strength of the refutation. Rubric: R1, R2, R7, R9, R12, R13 fail. D1-D5
all pass.

Provenance note: this lane's output file echoes the whole rendered prompt, so
the first consolidation run scraped four lines out of the output-format
examples inside that echo and ranked them as findings, including a spurious
🔴 "SQL injection in query builder | src/db/query.ts". Those are template
text. The table in the detail report is the re-run over the lanes whose files
hold findings only.

## Carl

**00266-bind-gate-reuse-to-the-command-and-renames-v1-c1**

8 findings, all 🟡, overlapping Bob and Alice: staging refusal exit 1 vs 2;
`mkdir` before the containment check; `-uall` and the missing pathspec;
`gate_command` optional; the prefix computation being redundant with
`git --relative` and pathspecs; `stage` at 54 lines; `reuse_verdict` at 54
lines; `test_review_stage.py` at 842 lines. All but the #16-scoping rows were
fixed in rework.

Verdict: converged
Tests: 2832 passed, 0 failed, 0 skipped (fast-track batch suite)
codex_rung_guard: not fired
