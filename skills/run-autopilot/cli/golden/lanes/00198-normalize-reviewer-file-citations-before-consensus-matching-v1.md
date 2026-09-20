---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription - the regex, the normalization steps and the persona sentence are given verbatim; the named fixture from review 00186 fails until they land
---

# Normalize reviewer file citations before consensus matching

Source: `dev/local/reviews/00186-add-item-grained-fast-track-lane-v1-review-1.md`
§ Consolidated Findings (2026-09-07) and
`dev/local/notes/autoclaude-inefficiencies-2026-09-13.md` finding 8. Advisory
discovery gate skipped: the defect is reproduced by a fixture the review file
already contains.

## Problem

`consolidate_findings.py` merges two findings only when `files_match` holds.
`normalize_file` strips a trailing `:N` or `:N-M` (`_TRAILING_LINENO_RE`), but
Alice cites files as absolute paths with a parenthesised range,
`/Users/.../skills/fast-track/SKILL.md (lines 166-171)`, while Bob cites
`skills/fast-track/SKILL.md:166`. The ` (lines 166-171)` suffix survives, the
last path segment becomes `SKILL.md (lines 166-171)`, and the tail comparison
fails. Review 00186 cycle 1 reports four genuine [2/4] agreements rendered as
[1/4]; the decision gate re-derived them by hand. Consensus drives task
priority and the scope alarm, so an under-count changes what gets reworked.

## Solution

Widen the normalization to every citation shape the personas emit, and pin the
citation format in the personas so the drift stops at the source.

## Requirements

### Must have
- `_TRAILING_LINENO_RE` becomes
  `re.compile(r"(?:\s*\(lines?\s+\d[\d,\s-]*\)|:\d+(?:-\d+)?)$")` (one
  anchored alternation; the parenthesised form accepts comma-separated
  ranges such as `(lines 18-22, 423)`, which is what Alice writes in
  `dev/local/notes/00198-fixture-reviewer-outputs-00186/alice-output-00186c1.txt:5`),
  and `normalize_file` applies it in a loop until the string stops changing.
  The loop is required, not optional: a citation can carry both forms
  (`a.md:12 (lines 3-4)`), and today's single `.sub()` at
  `consolidate_findings.py:145` strips only the outermost.
- `normalize_file` also drops a leading `L` line marker form `#L12-L20` and
  `#L12`, and lower-cases only after suffix removal (unchanged order).
- New test cases in `test_consolidate_findings.py`:
  `test_parenthesised_line_range_resolves_to_the_same_file` (the two 00186
  citations above match), `test_comma_separated_ranges_are_one_suffix`
  (`SKILL.md (lines 18-22, 423)` and `SKILL.md:18` match),
  `test_hash_line_anchor_resolves_to_the_same_file`,
  `test_both_suffix_forms_on_one_citation_are_stripped`,
  `test_a_directory_named_lines_is_not_a_suffix` (`docs/lines/notes.md`
  keeps its path).
- `agents/alice.md`, `agents/blake.md`, `agents/carl.md` and the Bob prompt in
  `skills/review-work-completion/references/agent-invocation.md` gain the
  sentence: `Cite files repo-relative as path:line (for example
  skills/work/SKILL.md:166), never absolute and never with a "(lines a-b)"
  suffix.` A prose test `test_citation_format_prose.py` pins it in each.

### Nice to have
- `render` prints a one-line stderr note when two findings in one row cite
  paths that only matched after suffix stripping, so a future drift is visible
  in the review file's script-output block.

## Implementation

### Module: consolidate_findings
- **Location**: `skills/review-work-completion/scripts/consolidate_findings.py`
- **Responsibility**: merge reviewer findings that describe one defect
- **Exports**: `normalize_file()`, `files_match()`

### Module: reviewer personas
- **Location**: `agents/*.md`, `skills/review-work-completion/references/agent-invocation.md`
- **Responsibility**: the citation format each lens emits
- **Exports**: none (prose pinned by `test_citation_format_prose.py`)

### Dependencies
- consolidate_findings: No dependencies (foundation)
- reviewer personas: No dependencies (independent prose)

## Tasks

### Phase 0: Foundation
- [ ] Widen `_TRAILING_LINENO_RE` and `normalize_file` - the four new cases
  pass; `test_same_basename_in_different_directories_is_not_the_same_file` and
  `test_path_tail_and_line_suffix_resolve_to_the_same_file` still pass.

### Phase 1: Core
- [ ] Add the citation sentence to the four personas (depends on: none) -
  `test_citation_format_prose.py` finds `path:line` and `never absolute` in
  each file; `skills/review-work-completion/scripts/test_agent_registry.py`
  stays green.
- [ ] CHANGELOG `### Fixed` entry under `**review-work-completion**`
  (depends on: Phase 0) - `rg -c "consensus.*citation|lines a-b" CHANGELOG.md`
  returns 1 or more.

## Success Criteria

- `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_consolidate_findings.py skills/review-work-completion/scripts/test_citation_format_prose.py`
  green.
- Replaying the four 00186 reviewer output files (durable copies in
  `dev/local/notes/00198-fixture-reviewer-outputs-00186/`; the implementer
  copies them into `skills/review-work-completion/scripts/fixtures/review-00186/`
  as part of Phase 0) through `consolidate_findings.py` yields the four rows
  the review file lists under "Real consensus" at `[2/4]`; recorded as a
  fixture-backed case `test_review_00186_agreements_merge` that passes
  `total_agents=4` explicitly, because the Carl fixture holds no findings
  (`carl-output-00186c1.txt:198` is `[CARL] No issues found`) and the four
  agreements come from Alice (6 findings) and Bob (23).
