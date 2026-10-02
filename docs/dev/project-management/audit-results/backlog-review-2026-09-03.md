# Backlog review - claude-autopilot - 2026-09-03

Verdict: GO (after the apply pass below; 0 Blocking open, no reshapes)

Inventory: `backlog/` holds 00170, 00171, 00173; `wip/` empty; `hold/` holds 00110;
`discovery/` holds 00157. Sequence numbers unique across all dirs. No live
autopilot loop (`pgrep` empty). check_links: two hits in backlog, both on 00170
(line 98 glob, waiver token on the wrong line; line 243 the PRD's own output).
Law read live: `create-prd/SKILL.md` + `assets/{minimal,standard,example_prd_rpg}.md`.
Budget rules read from the installed plugin `autopilot/0.4.1` plan-tasks steps 4-4.7
(150K per task, one split attempt, then `hold/`).

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00170 | tune-routing-from-outcomes-v1 | standard | 276 | run-autopilot: `cli/statectl.py`, new `scripts/tune_routing.py`, `references/{state-schema,model-ladder}.md` | none (reads `tasks[].tier_reason` from done 00160) | FIX |
| 00171 | route-sonnet-prompt-through-stdin-v1 | standard (partial) | 66 | use-sonnet: `sonnet-run.sh`, `test_sonnet_run.sh` | none | FIX |
| 00173 | guard-the-canonical-read-in-the-doctor-verdict-v1 | standard (partial) | 65 | use-codex: `codex_hook_doctor.py`, `test_codex_hook_doctor_extra.py` | none (00169 done) | FIX |

Grounding verified with `rg` (all true today): classifier constants at
`classify_tier.py:76-77`; `append_attempt_rows` row dict holds exactly the eight
keys 00170 names (`statectl.py:398-407`); `model-ladder.md` § Per-rung budgets
(l.44, Repair row l.52) and § Kill-switches (l.235); `_PLAN_TASKS_FLOOR` is a
prose-only knob no script reads (`plan-tasks/SKILL.md:270`); `state-schema.md`
§ Attempt ledger dedupe key (l.249) and the `tier_reason` enum (l.187); ledger
has 11 rows; `sonnet-run.sh:232` is `"$PROMPT" < /dev/null`, guard at l.224; the
five test case names 00171 quotes exist verbatim; `release-checks` runs the
sonnet test (l.22); doctor: unguarded canonical read at `codex_hook_doctor.py:79`,
except tuples at l.136/l.152, prefix at l.200, write-path read at l.209,
`_report` counts `no_canonical` with `stale` (l.389); `SKILL.md:119` documents
exit 3; `test_codex_hook_doctor_repair.py` is 795 lines, `_extra.py` 667;
`dev/local/reviews/00169-review.md` exists. Source discovery for 00170
(`~/.claude/.../00065-deepen-model-escalation.md` requirement 11) carried over,
with the propose-only decision recorded.

## Findings

### Blocking

- [00173] B executability: Feature "An unreadable canonical verdicts the target,
  not the run", Outputs: "the decision the PRD must make is which. Candidates:
  `no_canonical` ... or a new `canonical_unreadable` verdict"; Phase 0 task
  "Pick the verdict ... (default: `no_canonical`)". A decision deferred to
  implementation -> fails as: wrong-TDD lock-in (a new verdict string also
  touches `_report`, the SKILL.md exit list and two prose pins; the test author
  picks one from the task text). Fix: pin `no_canonical`, delete the candidates
  sentence, drop the conditional SKILL.md line from the tree, and state that the
  guarded read in `_repair_known` runs before the `dry_run` branch so
  `--dry-run` reports `unrepairable`, not `would-repair`.
- [00171] B executability: Feature "Prompt mode feeds the prompt on stdin",
  Behavior offers `<<< "$PROMPT"` OR `printf '%s' "$PROMPT" |`. A here-string
  appends one newline; printf appends none; the new case asserts byte equality
  with a fixture written without a trailing newline (`test_sonnet_run.sh:64`)
  -> fails as: wrong-TDD lock-in (the two mechanisms cannot both pass the pinned
  test). Fix: pin `printf '%s' "$PROMPT" |` and say the captured stdin equals
  the prompt bytes exactly.
- [00171] C coherence: `test_sonnet_run.sh` case 1 "claude child stdin is
  /dev/null" (l.83-91) asserts the stub captured 0 bytes; after the change the
  stub captures the prompt, so the case goes red, and the Feature "The argv pins
  follow" does not list it -> fails as: wrong-TDD lock-in / rework thrash (a
  plausible repair is deleting the guard, silently reopening the PRD 00040 hang
  class the Success Metrics promise to keep closed). Fix: add the case to the
  rewrite list with its new assertion: captured stdin equals the prompt and
  never contains `SENTINEL_STDIN_DATA`.
- [00170] B executability: Phase 2 task 2 "Run the tuner against this repo's
  real ledger and commit the output". `dev/local/` is gitignored
  (`.gitignore:6`), so the proposal cannot be staged; `work` step 5 stages the
  reported paths, the `git add` of an ignored path is rejected, one retry, then
  ESCALATE with `cause: "commit_rejected"` -> fails as: stall (`sub_skill_fail`
  in loop mode), or an improvised commit-less task the skill has no branch for.
  Fix: fold the real run into Phase 2 task 1's acceptance (that task commits the
  prose and CHANGELOG; the proposal is a run artifact whose path and per-signal
  lines go in the task report).

### Non-blocking

- [00170] A hygiene (mandated, applied without asking): check_links flags l.98
  (`dev/local/audit-results/audit-qwen-*.md`); the `link-ok:` waiver sits on
  l.99, not the citing line. Fix: move the token onto l.98.
- [00171] A compliance vs `standard.md` (mandated by create-prd "all four
  sections"): missing `### Repository Structure` heading, `### Module:` block,
  `## Dependency Graph`, Feature `Description` bullets, `### Critical
  Scenarios`. Machine impact none: installed plan-tasks derives structure when
  sections are absent (SKILL.md l.65), and nothing in the installed 0.4.1 pack
  parses `#### Feature:` headings. Fix: add the minimal headings.
- [00173] A compliance, same set plus missing `## Test Strategy` and the phase
  `**Goal**` line. Fix: add the minimal headings.
- [00170] F sizing: 276 lines against the 200-line split guide. One subsystem,
  three phases, contract-dense rather than prose-heavy (about 4K tokens of
  prose tax per task, far under the 150K cap). No split: Phase 0 alone is a
  two-key change too small to stand.
- [00171] B wording: "Interactive, resume and continue modes keep the TTY and
  the positional prompt" - `-R` is also a resume and stays on `--print`; name
  `-r` to avoid the misread. Folded into the printf edit.
- [all] Feature headings are unique per PRD; task lines all carry
  `Acceptance:`; frontmatter values valid (00171, 00173: `catchup: skip`,
  `design: skip`; 00170: none, defaults fit a new script).

### Questions

- [00170] C coherence: S1 counts rows while `task_tier_reason` is per task. An
  escalated mechanical task writes two rows (haiku `outcome: "escalated"`, then
  sonnet `escalation_reason: "gate_failure"`), both counted as escalations, so
  the rate and the 12-row floor are inflated (k escalated + k clean tasks reads
  0.67, not 0.5). Intent: per row or per task? Candidate fix: restrict S1 to
  `attempt.attempt == 1` rows, rate = share with `attempt.outcome ==
  "escalated"`.
- [00171] G gaps: the same positional-prompt shape lives in `codex-run.sh`
  l.244 and l.304 (`"$PROMPT" < /dev/null` to `codex exec`) and `gemini-run.sh`
  l.218/229/250/266 (`-p "$PROMPT"`, where a yargs-style parser may read a
  dash-leading value as a flag). 00171 names gemini as out of scope and does not
  name codex. Widen 00171, file a follow-up, or accept?

## Reshapes

None. 00171 and 00173 are single-task fix PRDs with their own regression tests
in different skills; merging them would put unrelated diffs under one review.

## Gaps

- The leading-dash prompt class in `codex-run.sh` and `gemini-run.sh` (above);
  whether `codex exec` and `gemini -p` read a prompt from stdin is unverified
  and is the premise a follow-up must check first.
- 00170's proposal file names the newest `audit-qwen-*.md`; none exists in this
  repo yet (the PRD handles absence). Not a hole.

## End state after this batch

The attempt ledger becomes attributable (every row names the plan-time rule),
and a stdlib tuner turns it into a propose-only file with honest HOLDs, so the
mechanical row, the repair budget and the codex rung get tuned from data
instead of by hand. The sonnet runner stops rejecting prompts that open with a
dash, and the codex hook doctor never aborts a run on a directory, unreadable
or null-byte canonical. Left half-finished: the same prompt-delivery class in
the codex and gemini runners, and the tuner's first real run will HOLD on every
signal until roughly a dozen attributable rows exist.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00170 | none | new script plus a schema change; the default design and rework cap fit |
| 00171 | none | already `catchup: skip`, `design: skip` |
| 00173 | none | already `catchup: skip`, `design: skip` |

## Decisions applied

| # | PRD | Decision | Status |
|---|-----|----------|--------|
| 1 | 00173 | Pin `no_canonical`; guarded read before the `dry_run` branch; SKILL.md dropped from the tree; Phase 0 renamed "Guard the reads" | applied |
| 2 | 00171 | Pin `printf '%s' "$PROMPT" \|`; `-r`, `-c`, `-i` named explicitly; `-S`/`-R` stay on `--print` | applied |
| 3 | 00171 | Case 1 rewritten to "claude child stdin is exactly the prompt, never the wrapper's stdin" (equals prompt bytes, no `SENTINEL_STDIN_DATA`) | applied |
| 4 | 00170 | Phase 2 task 2 deleted; the real run folded into Phase 2 task 1's acceptance; the proposal is a run artifact, never staged | applied |
| 5 | 00170 | S1 restricted to `attempt.attempt == 1` rows, rate = share with `outcome == "escalated"`; fixture and happy-path text follow | applied |
| 6 | 00171 | Same prompt-delivery class in `codex-run.sh` (l.244, l.304) and `gemini-run.sh` (`-p`): follow-up PRD after this batch; premise to check first is whether `codex exec` and `gemini -p` read a prompt from stdin | deferred, home: this report |
| M1 | 00170 | `link-ok:` token moved onto the citing line (l.98) | applied (mandated) |
| M2 | 00171 | `### Repository Structure`, `### Module: sonnet-runner`, `## Dependency Graph`, Feature `Description`/`Behavior` bullets, `### Critical Scenarios` added | applied (mandated) |
| M3 | 00173 | Same set plus `## Test Strategy` and the Phase 0 `**Goal**` | applied (mandated) |

Post-apply checks: heading walk against `standard.md` passes on all three;
`check_links` on `backlog/` reports only 00170 l.248 (`routing-proposal-<today>.md`,
the PRD's own declared output); no `TBD`/`TODO`/`???`/placeholder markers; no
reference to the deleted task or the dropped verdict candidate. Line counts:
00170 281, 00171 84, 00173 94.

Per-PRD verdicts after apply: 00170 READY, 00171 READY, 00173 READY.
