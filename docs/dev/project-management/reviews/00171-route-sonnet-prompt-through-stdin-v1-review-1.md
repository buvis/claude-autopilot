---
prd: dev/local/prds/wip/00171-route-sonnet-prompt-through-stdin-v1.md
review: 1
date: 2026-09-05
head_sha: b231d0da5e772aef3c20445ad73d0e7123d94fe1
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
---

# Review: 00171-route-sonnet-prompt-through-stdin-v1

Diff range: `862d1980c3133a7ffad115037e683bc0c55b7c51..b231d0da5e772aef3c20445ad73d0e7123d94fe1`

codex_rung_guard: not fired

pack: unavailable (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every `{PACK_FILE}` / `{PACK_FINDINGS}` slot carried the sentinel `(no pack available this cycle)`.

## Scope note

The recorded PRD work range `work_start_sha..HEAD` also contains `e5d6a4a
feat(run-autopilot): propose routing changes from the attempt ledger`, which
belongs to the concurrent PRD 00170. The reviewed diff was therefore path-scoped
to PRD 00171's own surface — `skills/use-sonnet/` and `CHANGELOG.md` — across
commits `20be167` (tests) and `b231d0d` (fix). Uncommitted working-tree changes
under `skills/run-autopilot/scripts/` (PRD 00170, in flight) were left untouched
and unreviewed. This continues the build phase's recorded autonomous decision 2.

## Reviewer availability

- **Alice** (consensus, Claude subagent): ✅ available.
- **Blake** (blind lens, PRD-only Claude subagent): ✅ available.
- **Bob** (doubt + de-slop lens): ✅ available **via the mandated Claude fallback**.
  The codex CLI refused dispatch with exit 3 — `refusing nested dispatch (already
  inside a CLI agent)`. This headless session's environment carries a complete
  codex marker set (`CODEX_SESSION_ID`, `CODEX_THREAD_ID`, `CODEX_CI=1`), which
  trips `codex-run.sh`'s recursion guard. The guard was **not** bypassed; Bob's
  assembled doubt prompt was run on a Claude subagent instead, so the doubt lens
  did not drop. No `codex_thread_id` was captured this cycle, so cycle 2 (if any)
  runs Bob fresh.
- **Carl** (Gemini/copilot): ⚠️ unavailable — `gemini-run.sh` exited 3 with the
  same nested-dispatch refusal. Skipped as documented graceful degradation.
  Consensus therefore scales to 3 reviewers, not 4.

**Operator note (not a PRD 00171 finding):** the same inherited
`CODEX_SESSION_ID` is what the build phase worked around when it ran
`env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH bash
dev/bin/release-checks` (recorded in `last-verification.json`), and Blake hit it
independently inside his own subagent. It is not recorded in
`ledger/attempts.jsonl` or `dispatch-metrics.jsonl`. While it persists, every
review cycle in this batch loses the codex and gemini lanes.

## Consolidated Findings

Consolidation ran through `consolidate_findings.py` (3 agents; no ledger file —
cycle 1). No Critical and no High finding was raised by any reviewer.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/3] | 🟡 Medium | The canonical shared dispatch contract still says headless children get `< /dev/null` and that prompts "pass via argument or `-f` file, never stdin"; sonnet's `--print` path now contradicts both sentences, and that file declares itself the winner on disagreement, so the next maintainer reading it will revert this fix | skills/use-codex/references/dispatch-contract.md | 1 | Bob |
| [1/3] | 🟡 Medium | "Byte-exact" is pinned only for fixtures with no trailing newline; `PROMPT=$(cat "$PROMPT_FILE")` strips trailing newlines, so a normal prompt file ending in `\n` is delivered one byte short, and the PRD's own risk note ("the leading-dash case asserts byte equality so any trim shows up") cannot fire against a fixture written with `printf '%s'` | skills/use-sonnet/scripts/test_sonnet_run.sh | 1 | Bob |
| [1/3] | ⚪ Low | CHANGELOG says the -f prompt file is "streamed byte-exact," but the pre-existing `PROMPT=$(cat "$PROMPT_FILE")` (sonnet-run.sh, unchanged by this diff) strips a trailing newline via command substitution; a prompt file ending in a newline loses it before reaching claude, so "byte-exact" only holds for files without a trailing newline. Not a regression from this diff — flagging only because the new sentence is the diff's own claim. | CHANGELOG.md | 1 | Alice |
| [1/3] | ⚪ Low | Test case labels in test_sonnet_run.sh (e.g. "plain -f sends the prompt bytes exactly on claude stdin") diverge from the exact strings the PRD prescribes ("claude child stdin is exactly the prompt, never the wrapper's stdin"), though the assertions are behaviorally equivalent or stricter (byte-exact cmp). | skills/use-sonnet/scripts/test_sonnet_run.sh | 1 | Blake |
| [1/3] | ⚪ Low | Assertion 1's FAIL message lost its observed-value diagnostic (the old one printed the captured byte count); it now restates the expectation without any evidence, unlike every other FAIL in the file | skills/use-sonnet/scripts/test_sonnet_run.sh | 1 | Bob |
| [1/3] | ⚪ Low | Cannot statically verify: `bash skills/use-sonnet/scripts/test_sonnet_run.sh` and `bash dev/bin/release-checks` green, and that the new leading-dash case was watched failing against the pre-fix script | N/A | 1 | Bob |
| [1/3] | ⚪ Low | The pipe introduces a SIGPIPE/pipe-buffer failure mode the stub cannot model: under `set -eo pipefail`, if the real `claude` exits 0 without draining a prompt larger than the 64 KiB pipe buffer, `printf` dies 141 and the wrapper reports 141 for a successful run; reviewer prompts that inline a diff routinely exceed that size | skills/use-sonnet/scripts/sonnet-run.sh | 1 | Bob |
| [1/3] | ⚪ Low | No test exercises the interactive (`-i`) path that the PRD requires to keep the TTY and the positional prompt, so nothing pins the boundary the fix must not cross | skills/use-sonnet/scripts/test_sonnet_run.sh | 1 | Bob |

**Note on Bob's "Cannot statically verify" line.** It is his sandbox marker for
runtime claims. Both runtime claims it names were in fact verified live this
cycle by two other reviewers: Alice and Blake each ran
`bash skills/use-sonnet/scripts/test_sonnet_run.sh` (25 passed, 0 failed) and
Blake ran `bash dev/bin/release-checks` green end to end; Alice additionally ran
the new test file against the pre-fix script at `20be167^` and observed 7 of 25
failing, which is the fail-first evidence the finding asks for.

**Follow-up tasks:** none created here. All eight findings are Medium or Low, so
the cycle converges and the Phase 5 tail sweep owns task creation — one
`[D1]` task carrying the `### Findings (verbatim)` block. Creating tasks in this
step as well would double-book the same findings.

## Alice

Consensus lens, implementation-aware. Verified the production change is confined
to the `prompt)` case's dispatch line; interactive/resume/continue branches
untouched; `-S`/`-R` still on the `--print` path; the empty-prompt guard
unchanged and still ahead of dispatch. Confirmed the acceptance grep
`rg -n '"\$PROMPT" < /dev/null' skills/use-sonnet/scripts/sonnet-run.sh` has no
hit. Ran the suite: 25 passed, 0 failed. Verified fail-first by running the new
test file against the pre-fix script (`20be167^`): 7 of 25 failed, including the
new leading-dash case. Confirmed the commit split is clean (`20be167` tests only,
`b231d0d` script + CHANGELOG) and that every caller uses the unchanged `-f`
public surface. Confirmed no unrequested `-f` direct-file special case survives.

- ⚪ CHANGELOG "streamed byte-exact" overstates what the code keeps, because the
  pre-existing `PROMPT=$(cat "$PROMPT_FILE")` strips a trailing newline.
  File: CHANGELOG.md

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

## Blake

Blind lens — PRD only, no diff, no file list, no review history. Located the
code himself. Verified the dispatch line, the acceptance grep, the suite (25/25
including T18 leading-dash and T19 empty-prompt), and `dev/bin/release-checks`
green end to end. Confirmed `gemini-run.sh` (explicitly out of scope per the
PRD's Risks section) was not touched.

- ⚪ Test-case labels diverge from the exact strings the PRD prescribes, though
  the assertions are behaviorally equivalent or stricter (byte-exact `cmp`).
  File: skills/use-sonnet/scripts/test_sonnet_run.sh

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

## Bob

Doubt + de-slop lens, run on the Claude fallback after codex refused dispatch
(see Reviewer availability above). Six findings: two Medium, four Low.

- 🟡 `skills/use-codex/references/dispatch-contract.md` still mandates
  `< /dev/null` and "never stdin", and declares itself authoritative on
  disagreement — so the contract now contradicts the shipped fix.
- 🟡 The trailing-newline strip is unpinned; the "byte-exact" claim only holds
  for fixtures written without a trailing newline.
- ⚪ Assertion 1's FAIL message lost its observed-value diagnostic.
- ⚪ Cannot statically verify the suite/gate/fail-first claims (sandbox marker;
  answered live by Alice and Blake, see the note above).
- ⚪ SIGPIPE/pipe-buffer failure mode under `set -eo pipefail` for prompts larger
  than the 64 KiB pipe buffer if `claude` exits without draining.
- ⚪ No test exercises the interactive (`-i`) path the fix must not cross.

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

### Doubt buckets

FIX:
- Dispatch contract contradicts the new stdin shape — skills/use-codex/references/dispatch-contract.md:17 and :21 — add one sentence to "Child Stdin Policy" recording the use-sonnet prompt-mode exception (child stdin is the prompt bytes from a `printf` pipe, which closes at EOF and so still forecloses the PRD 00040 hang class), and qualify line 17 as "callers pass prompts via argument or `-f`, never by piping into the run script".
- Trailing-newline strip is unpinned and the CHANGELOG overstates it — skills/use-sonnet/scripts/test_sonnet_run.sh:64,347 and CHANGELOG.md:23 — add a case whose fixture ends in `\n` and assert stdin equals the file minus its final newline, and change "streamed byte-exact" to a claim the code actually keeps.
- FAIL message with no evidence — skills/use-sonnet/scripts/test_sonnet_run.sh:88 — append the observed capture.

VERIFY:
- Suite and gate green, regression watched red first — **not queued: command shape** (multi-command chain, not one runnable command). Already answered live this cycle: Alice and Blake both ran the suite (25 passed, 0 failed), Blake ran `dev/bin/release-checks` green, and Alice observed 7 of 25 failing against the pre-fix script.
- Large-prompt pipe behavior (>64 KiB prompt against the real `claude`) — **not queued: command shape** (a live model dispatch with a fabricated fixture is not a project verification command). Carried as the ⚪ Low SIGPIPE finding instead.

KNOWN:
- No `-i` interactive test — pre-existing gap in the harness, untouched by this diff; the PRD lists only the five `--print`-path cases plus the leading-dash and empty-prompt cases, so adding interactive coverage is new scope rather than a regression from this change.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

⚠️ Unavailable this cycle. `gemini-run.sh` exited 3 with
`refusing nested dispatch (already inside a CLI agent)`. Skipped per the skill's
graceful-degradation rule; no findings, no verdict lines.

Verdict: 8 findings
Tests: 201 passed, 0 failed, 0 skipped (reused from last-verification.json at b231d0da5e772aef3c20445ad73d0e7123d94fe1)
