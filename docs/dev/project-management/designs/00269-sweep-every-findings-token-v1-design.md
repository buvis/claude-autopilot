# Design: Sweep every findings token

PRD: `docs/dev/project-management/prds/wip/00269-sweep-every-findings-token-v1.md`

## Architecture fit

This lands entirely inside `skills/run-autopilot/cli/`, the sole `state.json`-mutator surface, plus two downstream prose/test trees that describe its contract:

- `gate.py` — owns `findings_verdict`/`_cross_check_findings`, the regex constants (`_FINDINGS_HEADING_RE`, `_FINDING_ROW_RE`, `TABLE_DATA_ROW_RE`, `_FINDINGS_PROBLEMS`), and `_findings_exit`'s routing. This PRD adds the fence-aware scan, section-bounds rework, the unconsumed-token refusal, the no-section rule, and the ref-required hint — all behind `findings_verdict`, so `gate --findings` and `review_close.close()` read one rule.
- `review_close.py` — `_findings_refusal` already maps `gate.findings_verdict` tags to refusal kinds; this PRD changes that mapping (every `malformed` detail except `no-section` refuses `findings_malformed`), adds the `no_verdict` refused kind ahead of the shape gate, and rewrites `_carry_unmatched`/`_carry_refusal` into `_carry_reason` with the closest-task message.
- `__main__.py` and `review_stage.py` — `_stage_inputs_from_state`'s path refusal text, and `_tmp_escape_refusal`'s exit code, both get touched; these are CLI-surface refusal wording/exit-code fixes, not new logic.
- `skills/review-work-completion/scripts/gather-context.sh` — the `--since` resolution (`cat-file -e` → `rev-parse --verify --quiet ...^{commit}`) and the two `git diff` calls lose their `2>/dev/null || echo "_No diff available_"` swallow.
- Test files `test_gate.py`, `test_gate_findings_shapes.py`, `test_main_review_close_validation.py`, `test_review_close.py`, `test_review_close_carry.py`, `test_review_stage_paths.py`, `test_gather_context_id.sh`, `test_review_verbs_prose.py` carry the new/edited acceptance tests the PRD's Implementation Phases name.
- Prose files `CHANGELOG.md`, `skills/run-autopilot/references/phase-review.md`, `skills/review-work-completion/references/output-formats.md`, and the `00266-...-review-1.md` correction record the final behaviour truthfully.

No new modules, no new files (per the PRD's Repository Structure note); `gate.py` must stay ≤800 lines and `test_review_close.py` stays untouched at 764 (new review-close tests go in `test_main_review_close_validation.py` / `test_review_close_carry.py`).

## Module placement

New files: none.

Edited files (exact paths, PRD's own enumeration):

```
CHANGELOG.md                                                          # line 14 fix + new [Unreleased] lines
docs/dev/project-management/reviews/
└── 00266-bind-gate-reuse-to-the-command-and-renames-v1-review-1.md   # dated correction under Bob and Carl
skills/run-autopilot/cli/
├── gate.py                                   # fence scan, section bounds, unconsumed-token refusal, no-section rule, exit routing, ref-required hint
├── review_close.py                           # findings_malformed routing, no_verdict kind, carry match + closest-task message
├── __main__.py                               # review-stage path refusal text, gate/review-close help text
├── review_stage.py                           # _tmp_escape_refusal exit 2
├── test_gate.py                              # repoint one exit-1 test to exit-2
├── test_gate_findings_shapes.py              # new sweep tests (gate side), exit table case, ref-required hint test
├── test_main_review_close_validation.py      # both-verb sweep tests, no_verdict test, ref-required hint test
├── test_review_close.py                      # repoint the legacy applies-as-malformed test, _carry_reason call sites
├── test_review_close_carry.py                # carry match and closest-task message tests
└── test_review_stage_paths.py                # exit-2 and path-message tests
skills/run-autopilot/references/
└── phase-review.md                           # drop the "[D name test" clause from the carry-rule prose
skills/review-work-completion/
├── references/
│   └── output-formats.md                     # fence-example-rows guidance under the Ref paragraph
└── scripts/
    ├── gather-context.sh                     # ^{commit} check, loud diff failure
    ├── test_gather_context_id.sh             # two new PASS cases
    └── test_review_verbs_prose.py            # help/prose/CHANGELOG pins
```

## Interfaces & contracts

### Fence-aware line classifier (new, `gate.py`)

A per-line `quoted: bool` classification over `text.splitlines()`:

- A line whose **stripped** text starts with `` ``` `` (3+ backticks) or `~~~` (3+ tildes) OPENS a fence.
- The fence CLOSES on a later line whose stripped text starts with the same character, repeated at least as many times as the opener.
- Lines from the opener through the closer, both inclusive, are `quoted = True`.
- An unclosed fence (no closing line found) quotes NOTHING — every line after the opener (including the opener itself, per "cannot hide a row") stays live/`quoted = False`.
- HTML comments (`<!-- ... -->`) do NOT quote; a one-line comment containing a token is a live token line and must be consumed or it refuses.
- A quoted line is never: a token line, a row the parser reads, a findings heading, or a section-ending `## ` line.

Suggested shape: `_quoted_lines(text: str) -> list[bool]` returning one bool per line of `text.splitlines()`, consumed by both section-bounds and the token sweep so they agree on what is live.

### Section bounds (reworked, `gate.py`)

- Heading regex stays exactly `_FINDINGS_HEADING_RE = re.compile(r"^##\s+Consolidated Findings\s*$", re.MULTILINE)`, but the search is restricted to LIVE lines only (quoted lines are skipped when matching).
- A second LIVE findings heading makes the file unreadable (new case — today only the first match is taken).
- The section ends at the next LIVE `^##\s` line (today's `_NEXT_H2_RE = re.compile(r"^##\s", re.MULTILINE)` search must likewise skip quoted lines) — so a fenced `## example` line inside the section no longer ends it.

### Unconsumed-token refusal (new, `gate.py`)

- Inputs: the live lines, and the set of line numbers the parser consumed — i.e., every line matched by `_FINDING_ROW_RE` (the bullet rows) plus the header row, the separator row, and every data row the recognised table consumed (`_table_keys`'s header/`_CANDIDATE_ROW_RE`/`_TERMINATED_ROW_RE` matches).
- A LIVE line is a **token line** when it contains the regex `\[\d+/\d+\]` anywhere, OR its stripped text starts with `|`.
- Any token line not in the consumed set triggers the refusal:
  - `("malformed", detail)`
  - `detail = f"line {n}: a [m/n] token or table row the findings parser did not read: {line_stripped_cut_to_120_chars}"` — naming the FIRST such unconsumed line (1-indexed `n`).
- Triggers explicitly named by the PRD: a row above the table header, a `*`/`+` bullet row, a one-line `<!-- ... -->` row, a second table, every line under an unrecognised header (00268's shape), and any token OUTSIDE the section (e.g. under `## Alice` or `## Follow-up Tasks Created`).

### No-section rule (reworked, `gate.py`)

With no LIVE findings heading at all:

- Zero token lines in the whole file AND the findings JSON is empty (`findings == []`) →
  `("malformed", _FINDINGS_PROBLEMS["no-section"])` — the only verdict still eligible for exit 1 / legacy-apply.
- At least one token line anywhere → the unconsumed-token detail above (exit 2 territory).
- Zero token lines but a NON-EMPTY findings JSON → new `_FINDINGS_PROBLEMS` entry:
  `f"no '## Consolidated Findings' section, yet the findings JSON names {k} rows: the findings heading is missing or misspelled"` where `k = len(findings)`.

### Fail-closed exit routing

`gate._findings_exit(text, findings_file) -> int`:
- Returns `1` **only** when `detail == _FINDINGS_PROBLEMS["no-section"]`.
- Every other `malformed` detail returns `2` (replaces today's `2 if detail == _FINDINGS_PROBLEMS["unreadable-table"] else 1` at line 583).

`review_close._findings_refusal` / its `_FINDINGS_REFUSALS` mapping:
- Refuses `"findings_malformed"` for every `malformed` detail EXCEPT the `no-section` text, which keeps today's legacy-apply path (`findings_cross_check: "malformed"` recorded, nothing applied, since the findings JSON is empty by construction of that one surviving case).

### No-Verdict refusal exits 2 (`review_close.close`, packet 13)

`review_close.close()` must check `gate.VERDICT_RE.search(text)` BEFORE the existing shape gate (`_gate_review` → `gate.check`). On no match:

```python
{"applied": False, "refused": "no_verdict", "reason": <gate.check's existing no-verdict text>}
```
i.e. reuse the exact string `gate.check` already produces: `"no verdict line (expected 'Verdict: converged' or 'Verdict: N findings')"`. CLI exit becomes 2 (today: 1, via the generic `{"applied": False, "reason": ...}` shape-gap path). All OTHER shape gaps (missing reviewer section, missing Tests line, codex-guard gaps) and `"already applied"` keep exit 1 unchanged.

### Staging escape exits 2 (`review_stage._tmp_escape_refusal`, packet 14)

Current code (line ~756-762): returns `{"ok": False, "error": ..., "exit": 1}`. Change the literal `"exit"` value to `2`. No other field changes. `review-stage`'s CLI wrapper already propagates `result["exit"]`, so no `__main__.py` change needed for this piece — only the dict literal in `review_stage.py` changes.

00266 review-file correction (two new lines, one under `## Bob`, one under `## Carl`, `Verdict:`/`Tests:` unchanged):
```
> **Correction (2026-10-10, PRD 00269):** the staging-refusal exit code (1 vs 2) was not fixed in the 00266 rework; PRD 00269 fixes it.
```

### Version-skew hint (`_FINDINGS_PROBLEMS["ref-required"]`, packet 15)

Append to the existing `ref-required` string:
```
"; review files from autopilot 0.9.0 or earlier have no Ref column; finish or restart the batch on one version"
```
Both `gate --findings` stderr and `review-close`'s `findings_ref_required` refusal reason show it (single source of truth: the dict value).

### Path refusal names the field (`__main__.py::_stage_inputs_from_state`, packet 17)

One stderr line per failing field, exact templates:
```
autopilot: review-stage: `prd` '<raw>' resolves to <resolved>, outside <wip>/ (<state>)
autopilot: review-stage: `design_doc` '<raw>' resolves to <resolved>, outside the repo <repo_root> (<state>)
```
where `<raw>` is the state's raw `prd`/`design_doc` string, `<resolved>` is its resolved absolute path, `<wip>` is the resolved wip dir, `<repo_root>` is the resolved repo root, and `<state>` is the `--state` path as given. Multiple failing fields each get their own line. Exit stays 2.

### `review_close` carry match (`_carry_unmatched`, packet 18)

Delete the clause `and not str(t.get("name", "")).startswith("[D")` from `_carry_unmatched` (review_close.py line 390). The match becomes exactly, in order:

1. `ref in [str(r).strip().upper() for r in (t.get("carry_refs") or [])]`
2. `t.get("carry_cycle") == cycle`
3. `str(t.get("id")) in rework_ids`
4. `t.get("escalation_reason") in ("review_flag", "fable_rescue")`
5. `t.get("status") != "completed"`

A task named `[D1] ...` that satisfies all five now backs the carry row — the former 6th `not name.startswith("[D")` clause is simply removed, not replaced.

### Closest-task carry message (`_carry_reason`, new helper replacing part of `_carry_refusal`, packet 16)

`_carry_refusal`'s `reason` string becomes one of exactly three shapes (`_carry_reason(row, cycle, tasks, rework_ids) -> str`):

- No usable ref: `"carry row ref (none): a carry row needs a ref to match a re-queued task"`
- Ref present, no task names it in `carry_refs`: `f"carry row ref {ref}: no task lists {ref} in carry_refs"`
- Ref present, at least one task names it, none fully match: `f'carry row ref {ref}: closest task {id} "{name}" fails {field}: {why}'`

"Closest" = among tasks whose `carry_refs` includes `ref` (condition 1 satisfied), the one passing the LONGEST run of conditions 2→3→4→5 in order (first failing condition determines rank; ties broken by first occurrence in `state.tasks`).

`<field>: <why>` exact literals:
- `carry_cycle: {value} is not {cycle}`
- `rework_task_ids: {id} is not listed`
- `escalation_reason: {value} is not review_flag or fable_rescue`
- `status: completed`

### Loud diff gathering (`gather-context.sh`, packet 19)

Replace the `cat-file -e` check:
```bash
if [[ -n "$SINCE_REF" ]] && git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$SINCE_REF^{commit}" >/dev/null 2>&1; then
```
(today: `git -C "$PROJECT_ROOT" cat-file -e "$SINCE_REF"`). On failure, keep the existing fallback warning verbatim: `"gather-context: --since ref ${SINCE_REF} does not resolve; using the branch base"`.

Both `git diff` calls (lines ~161 and ~165) drop `2>/dev/null || echo "_No diff available_"` (and the file-redirect form's `> "$DIFF_FILE" 2>/dev/null || echo "_No diff available_" > "$DIFF_FILE"`). A failing diff now exits with git's own exit code, git's stderr intact, and prints no file paths on stdout.

## Data flow

**gate.py / `autopilot gate --findings` path:**
review file text → `_quoted_lines(text)` (fence classification) → live-line section-bounds search (`_FINDINGS_HEADING_RE`/`_NEXT_H2_RE` restricted to live lines) → token sweep over live lines inside/outside the section (classify every `[m/n]`/`|`-leading live line as consumed-by-parser or not) → `_reviewed_keys`/`_table_keys` row extraction (unchanged internals, now only ever see a verified-consumed, in-bounds slice) → `_cross_check_findings` verdict tuple (`"ok"|"mismatch"|"uncovered"|"ref-required"|"malformed"`, detail) → `findings_verdict()` (unchanged public signature) → `_findings_exit()` routes: `malformed`+no-section-text → 1, everything else non-"ok" → 2, "ok" → 0.

**review_close.close():**
review file text → `gate.VERDICT_RE` check (new, ahead of shape gate) → no match → `{"refused": "no_verdict", exit 2}`; match → `_gate_review`/`gate.check` shape gate (unchanged, exit 1 on gap) → `_findings_refusal` calls `gate.findings_verdict` (same sweep as above) → verdict tag routes by its EXISTING kind, unchanged by this PRD, with one narrowed exception: a `malformed` tag refuses `{"refused": "findings_malformed", exit 2}` for every detail EXCEPT the legacy no-section text (that one case keeps today's apply-as-legacy path); `mismatch`/`uncovered`/`ref-required` tags keep their own pre-existing refusal kinds (e.g. `findings_ref_required`) and exit codes, untouched by the sweep — only the `malformed` tag's internal detail set grows and its exit-2 boundary moves. → `_prelock_refusal` → `_carry_refusal`/`_carry_reason` (new closest-task logic) on any `carry` row → `statectl.mutate()` applies, or the batch is refused before any lock is paid for.

## Reuse inventory

- `skills/run-autopilot/cli/gate.py:114-170` — `_FINDINGS_HEADING_RE`, `_NEXT_H2_RE`, `_FINDING_ROW_RE`, `TABLE_DATA_ROW_RE`, `_FINDINGS_PROBLEMS` already exist; this PRD extends/reuses them rather than introducing parallel constants. Use directly: restrict their `.search()`/`.findall()` calls to a live-only view of the text instead of replacing the regexes.
- `skills/run-autopilot/cli/gate.py:349-388` (`_table_keys`) and `:391-414` (`_reviewed_keys`) — existing row-extraction logic for both the bullet and table shapes; reuse unchanged as the "what the parser consumed" source — the new sweep needs to know which line numbers these functions' matches correspond to, so the simplest reuse is to re-derive consumed line numbers from the same `_FINDING_ROW_RE`/`_CANDIDATE_ROW_RE`/`_TERMINATED_ROW_RE`/header matches these functions already make, rather than writing a second consumption tracker.
- `skills/run-autopilot/cli/gate.py:505-527` (`_findings_exit`) and `review_close.py:503-530` (`_findings_refusal`) — both already route on `_FINDINGS_PROBLEMS["unreadable-table"]` identity, not string content; the new routing is a straight generalization of that same pattern (compare to `"no-section"` instead of `"unreadable-table"`), reusing the existing "compare against the exact dict value" idiom rather than inventing a new one.
- `skills/run-autopilot/cli/review_close.py:367-392` (`_carry_unmatched`) and `:395-417` (`_carry_refusal`) — reuse the existing 5-of-6-condition structure; only remove one clause and replace the single generic reason string with the closest-task message, not the match logic itself.
- `skills/review-work-completion/scripts/gather-context.sh:46-56` — an existing `git rev-parse --verify` pattern (used for `CURRENT_BRANCH` and the candidate-base loop) is the direct model for the new `--since` check; reuse the same `--verify --quiet ...` idiom rather than inventing a new validity test.
- `gate._split_severity_cell` is already reused cross-module by `review_close._severity_file_key` (review_close.py:420-429) — same "reuse the one normalizer" pattern this PRD should follow for any new cross-module string (e.g. if `_FINDINGS_PROBLEMS` strings need reuse in review_close's messages, import the dict, don't restate the text).

Searched and found NOTHING for:
- A pre-existing fence-aware / fenced-code-block line classifier anywhere in the repo: `rg -n "backtick|\`\`\`|fence" skills/run-autopilot/cli/gate.py`, `rg -rn "def.*fence|_fence|is_quoted|in_fence" skills/run-autopilot/cli/` — no hits. This capability is genuinely new.
- A generic "markdown section bounds between two `##` headings" helper outside `gate.py`'s own `_FINDINGS_HEADING_RE`/`_NEXT_H2_RE` pair: `rg -rn "NEXT_H2|section_bounds|next_heading" skills/run-autopilot/cli/` — only the existing gate.py constants, already covered above.
- A shared "closest match / best-partial-match" helper usable for the carry message: `rg -rn "closest|best_match|rank_match" skills/run-autopilot/cli/` — no hits; the closest-task ranking in `_carry_reason` is new logic, though it reuses the existing 5-condition tuple shape.

## Alternatives considered

1. **Regex-only sweep (smallest diff)**: extend `_FINDING_ROW_RE`/`TABLE_DATA_ROW_RE` to also match stray `[m/n]` and `|`-rows wherever they appear in the raw text, without fence-awareness or section-bounds rework. Smallest change, but it is exactly the shape PRD 00265 already tried ("patched shapes one at a time") and the problem statement shows it keeps missing new shapes (second heading, fenced `## example`, rows above the header, bullets with `*`/`+`, HTML-comment rows, unrecognised headers). Rejected: it treats symptoms, and the operator decision explicitly calls for "fix the class, not the shapes."
2. **AST-style markdown parse (e.g. via a markdown library)**: parse the file into a real block tree (headings, code fences, lists, tables as structured nodes) and walk it. Most robust against future markdown shapes, but adds a dependency this CLI tool doesn't otherwise have, is a much larger diff across `gate.py`'s existing line-oriented helpers (`_table_keys`, `_reviewed_keys` would need a full rewrite, not an extension), and the PRD's acceptance tests are written against exact line-number/line-text detail strings that a tree-walk would have to re-derive anyway. Rejected: disproportionate to the fix, and conflicts with the 800-line ceiling on `gate.py`.
3. **Fence-aware line-scan state machine (chosen)**: a single pass that tags every line quoted/live, then layers section-bounds and token-consumption checks on top of that live-line view, reusing the existing line-oriented regexes (`_FINDING_ROW_RE`, `TABLE_DATA_ROW_RE`, `_FINDINGS_HEADING_RE`) unchanged in shape. This is the PRD's own design. It costs more than option 1 (a real line classifier plus a consumed-line-number set, not just a wider regex) but that extra size is exactly what buys correctness on every shape in the problem statement: tokens outside the section (`## Alice`, `## Follow-up Tasks Created`), tokens under a wrong/typo'd heading, bullet-row and HTML-comment shapes the parser never matched, a second table, and fenced example rows that must NOT count. Option 1 would still miss all of these; option 2 would cost far more than this PRD's phase/file budget allows.

## Risks & edge cases

From the PRD's own `## Risks`:

- **False refusals on honest files**: a reviewer prose section or a `## Follow-up Tasks Created` line that happens to write `🟠 [4/4]` (real file `00223-...-review-1.md` does this) now refuses where it did not before. Accepted by the operator. Mitigation already in scope: the refusal detail names the exact line number and text, and `output-formats.md` gets writer guidance to fence example rows — one edit fixes the file. Design implication: the unconsumed-token detail string MUST always include the line number, per the exact template above, or this mitigation breaks.
- **Second tables inside the section** (e.g. `00186-...-review-1.md`'s "Full script output" table) now refuse too — intended, since a second table is by definition an unread row set that could hide a finding.
- **Edits to existing tests can silently weaken coverage**: every touched test in the Implementation Phases carries an `rg -c` premise check and an explicit stop-and-report rule if the premise doesn't hold. The design must not bypass those premises when implementing — they are the guard against a "fix" that quietly deletes a case instead of relocating it.
- **Exit-code change for callers**: no-section-with-findings-rows moves from gate exit 1 → 2, and no-Verdict moves from review-close exit 1 → 2. Both are documented as unreleased paths; `phase-review.md` already treats any non-zero exit other than `"already applied"` as a sub-skill failure, so no caller-side prose branch needs to change — but this design must not introduce a THIRD undocumented exit-code path while fixing these two, or the same caller assumption breaks again silently.
- **Likely next bug class after this one**: the PRD's own enumeration (heading typo, second heading, fenced lookalikes, skipped row shapes, unrecognised table headers, carry-name coupling, swallowed diffs) was already a second round after PRD 00265's shape-by-shape patches. The fence-aware state machine generalizes most of these, but a FIFTH "unrecognised shape" is still conceivable (e.g. a token inside a `<details>`/HTML block, or a nested fence inside a fence) — this design's section-bounds/token-sweep split keeps that risk contained to one place (`gate.py`'s sweep) rather than scattered, so a sixth fix stays a one-module change.
- **Shared-helper extraction risk**: if `review-work-completion` or another reviewer tool ever needs the same fence-aware sweep (e.g. to validate its own output before handing it to `review-close`), duplicating the sweep instead of extracting it into a shared helper would reintroduce exactly the "two verbs can disagree" bug this PRD fixes for `gate`/`review-close`. Not in scope here (no new files), but worth flagging for the next PRD that touches `review-work-completion`'s own findings-shaped output.

## Test strategy outline

Per the PRD's `## Implementation Phases` and `## Test Strategy`:

- **Happy path**: the real fixture `00256-review-1.md` and a fully-Ref-covered table still exit 0 from both verbs (regression guard against over-tightening); a closed-fence example row inside `## Alice` is not a finding, exit 0.
- **No-section edge case**: no heading, zero tokens, empty findings JSON → gate exit 1, review-close applies nothing, `findings_cross_check: "malformed"` (the one surviving legacy-apply path); no heading but a non-empty findings JSON → new detail text, exit 2 from both verbs.
- **Unconsumed-token error-payload classes** (each → exit 2 from both verbs, `state.json` byte-unchanged): heading typo/missing heading with a ref table present; a CRITICAL row only under a reviewer heading; a second live findings heading; a fenced `## example` heading inside the section (must NOT trigger — a negative case); a fenced example row (must NOT trigger); an unclosed fence before a 🔴 row (must trigger, since it quotes nothing); a row above the table header; a `*`/`+` bullet row; a one-line HTML-comment row; a row under an unrecognised header (the 00268 payload); a second table.
- **Carry-match edge cases**: a `[D1]`-named task with correct stamps now backs a carry row (regression against the removed name test); a fresh `[D]` task with no `escalation_reason` is still refused; a completed carry task is still refused; the closest-task message names the right task and the right first-failing field, parametrized across each of the 4 failing-field cases plus the two ref-less/no-task-lists-ref cases.
- **Honest-refusal classes**: no-Verdict-line file exits 2 with `refused: "no_verdict"`; the `ref-required` message carries the 0.9.0 version-skew clause in both verbs' output; the staging escape exits 2; the path refusal names the field, raw value and resolved path for both `prd` and `design_doc`.
- **Fence/diff edge cases**: a blob SHA passed to `--since` falls back to the branch base with the existing warning, scope line reads "full review"; a valid `--since` plus a deliberately-failing pathspec (`review-paths` marker holding `:(nosuchmagic)x`) exits non-zero with git's own stderr and no stdout paths; every pre-existing `test_gather_context_id.sh` case still passes.
- **Prose/CHANGELOG pins**: help text names the sweep detail template, the no-Verdict exit 2, and "no matching re-queued task" (replacing the removed `[C]`-prefix wording); `phase-review.md` no longer states the `[D` name-test clause; `output-formats.md` tells writers to fence example rows; `CHANGELOG.md`'s `[Unreleased]` no longer claims "refuses exactly what `autopilot gate` refuses ... every refusal exits 2" and instead states the one documented exception; the 00266 review file carries exactly 2 new correction lines with `Verdict:`/`Tests:` untouched.

Full acceptance-test names and exact `rg -c` premises are in the PRD's `## Implementation Phases`; this section groups them by scenario category rather than restating each line.

## Review log

- non-blocker: Design never states gate.py's post-change line count vs the 800-line ceiling — gate.py is 654 lines today (146 headroom), but no estimate of the new sweep's added lines is given.
- question: the HTML-comment "never quotes, always live" rule doesn't explicitly say such a line can never be in the consumed set, so a token inside one always refuses — worth one clarifying clause.
- non-blocker: the claim that review-stage's CLI wrapper "already propagates `result[\"exit\"]`" is asserted but not quoted from `__main__.py` the way the rest of the section quotes source.
- question: the closest-task tie-break for equal-rank carry candidates relies on "first occurrence in state.tasks" — confirmed sufficient, no doc change needed.

dispatch 1 (claude): cardinal-sin 0, blocker 0, non-blocker 2, question 2

- blocker (fixed): Data flow's review_close.close() path implied every non-ok verdict routes to findings_malformed; corrected to route by each verdict tag's existing kind, with findings_malformed narrowed to malformed-tagged, non-no-section details only.
- non-blocker: the exit-code risk analysis in Risks & edge cases should enumerate the review_stage._tmp_escape_refusal exit-1-to-2 change too, not just the two gate/review-close paths.
- question: Architecture fit says test_review_close.py "stays untouched at 764" but Module placement lists edits to its legacy test and _carry_reason call sites — means line-count-neutral edits, not zero edits; wording should say that explicitly.

dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 1, question 1

- resolved: the Data flow fix matches both Fail-closed exit routing and the Version-skew hint; findings_malformed stays scoped to malformed-tagged, non-no-section details, and mismatch/uncovered/ref-required keep their own pre-existing refusal kinds.

dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 1, question 0
