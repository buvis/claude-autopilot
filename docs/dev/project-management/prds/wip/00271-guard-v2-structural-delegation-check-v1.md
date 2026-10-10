---
design: run
default_model: opus
model_tier_rationale: an invented structural predicate where a miss lets a phase leave the session and a false deny breaks a build; replay over real dispatches is the acceptance
---

# Guard v2: a structural phase-delegation check

## Overview

### Problem Statement

PRD 00267 (unreleased) widened `hooks/guard_phase_delegation.py` with six more verbs. Two agoge runs found it now fails both ways. It refuses ordinary per-task prompts ("Complete the planning phase notes ...; task 3 only." to Ivan, "Do the work phase tests pass?") and agoge's own lanes: walter's replay of 1,112 real Agent dispatches has HEAD deny 18 against 0.9.0's 14, and the 4 new denials are agoge lanes (`agoge-2026-10-07-2.md`, Repeats). It still lets common handoffs through ("Run your work phase for PRD 00300 now.", "Kick off the work phase ...", `Run the work-phase ...`, a bare `/autopilot:work <path>` prompt, `Run “/autopilot:work” now.`, an absolute SKILL.md path, "This is not optional: run the work phase", Unicode dashes and invisible marks). Its deny message gives wrong advice to Ivan and never says which words matched. It crosses its 5 s hook timeout at about 7.8 MB because of a per-character negation lookahead. The next release is blocked on this PRD.

The operator walked both reports (minutes in `docs/dev/project-management/audit-results/agoge-2026-10-07.md` and `agoge-2026-10-07-2.md`, finding 21). Every decision below is settled; this PRD encodes them. Report 1 findings 6, 13 and 14 are already applied (the narrowing file is gated, `test_hook_registration.py::test_every_hooks_test_file_is_in_the_release_gate` pins every `hooks/test_*.py` into `dev/bin/release-checks`).

### Target Users

- Autopilot build sessions in loop mode (`_AUTOPILOT_LOOP` set): they need Ivan, Tess, Devon and worker dispatches to pass, and need one-round recovery when the guard refuses.
- agoge runs on this repo: their lanes quote trigger phrases on purpose.
- The operator: needs the CHANGELOG to state what the guard really does.

### Success Metrics

- `hooks/test_guard_phase_delegation_structure.py`, `hooks/test_guard_phase_delegation_dispatch.py`, `hooks/test_guard_phase_delegation_replay.py`, `hooks/test_read_input.py` and `dev/bin/test_replay_delegation_guard.py` pass; each new behavior test fails at base (exceptions named in task 8).
- `python3 dev/bin/replay_delegation_guard.py` over this repo's local transcripts exits 0: zero per-task, agoge or reviewer dispatches refused, and the four real 00242 delegations refused.
- `test_guard_time_per_mb_stays_under_the_baseline` passes (under 0.3 s per MB on the crafted prompt, so the 5 s budget is reached only past about 16 MB).

## Functional Decomposition

### Capability: Structural delegation check

Decide from the shape of a sentence, not from verb or gap-word lists, whether an Agent call hands a whole phase to a subagent.

#### Feature: Normalization

- **Description**: Turn lookalike text into the plain form before any matching.
- **Inputs**: `prompt` and `description` strings from `tool_input`.
- **Outputs**: normalized text per field.
- **Behavior**: `NFKD`, drop every code point whose `unicodedata.category` is `Cf` or `Mn`, map every `Pd` code point and U+2212 to `-`, then `NFKC`. Keep today's curly single quote map. Remove `*` emphasis markers. Homoglyphs (Cyrillic `о`) stay out of scope (packet 9).

#### Feature: Phase mention in object position

- **Description**: Find a phase or phase skill named as the thing to run.
- **Inputs**: normalized field text.
- **Outputs**: the first counting match (start offset) or none.
- **Behavior**: A phase name is `work phase`, `plan phase`, `planning phase` or `design phase` with `[-_ ]` between the words, `autopilot:work|plan-tasks|design-solution` with optional `/`, or bare `plan-tasks|design-solution` with a leading `(?<![-/\w])` and trailing `(?![-/.\w])` boundary. Optional backticks, quotes or brackets may wrap it and an optional ` skill` may follow. No verb list. The name is in object position when either holds:
  - strong anchor: it is followed by `for|on` (optional `the`) then `PRD`, `task`, a `<slug> PRD`, or a 3-5 digit number, or by `from task`; or its sentence also holds a whole-run marker (`every task`, `all tasks`, `all the tasks`, `keep going`, `until done|complete|finished`, `end to end`, `onward(s)`).
  - weak anchor: it ends its clause (optionally after a closing quote and one of `now|again|first|immediately|please|in full`), at least one word precedes it in the clause, and the nearest preceding word that is not a determiner is not a preposition (guess: determiners `the a an this that these those my your our its their next all of each every entire whole full remaining`; prepositions `in about of during before after from with by at into within without under over to for on through between across per via than like`).
  A clause that ends in `?` never counts. Quoted text gets no exemption: a quote around a phrase or a whole sentence is checked like any other text (operator decision 2026-10-10; agoge 2026-10-07 #7 rejected ignoring quoted text). Per-task personas (`autopilot:ivan`, `autopilot:tess`, `autopilot:devon`, any `autopilot:worker-*`) count the strong anchor only; the weak anchor never fires for them, because their prompts quote skill prose as edit targets. Evidence: the real worker-opus Ivan dispatch `toolu_01V199BvGGdSG4pvZ4B9Y1sT` quotes the product line "Invoke `/autopilot:work` skill. It runs until all tasks complete." as an insertion target; the name ends its clause (weak anchor) and the whole-run marker sits in the next sentence, so it passes under this rule without a quote exemption. The design step must confirm this against the replay fixture; if the rule fails there, it must find another rule that keeps quoted text checked.
  Clause boundaries are `. ; , : ! ? \n`, `)` and ` - ` (after dash mapping). Sentence boundaries are `. ! ? \n`.

#### Feature: Bare skill prompt and SKILL.md hand-over

- **Description**: Two forms that always delegate.
- **Inputs**: normalized field text.
- **Outputs**: a counting match or none.
- **Behavior**: A prompt whose first token is `/autopilot:(work|plan-tasks|design-solution)` is always refused, whatever scoping follows. A path matching `(?:\S*/)?(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md` (any prefix: absolute, `${CLAUDE_PLUGIN_ROOT}/`, relative) counts when the same sentence, within 200 characters after it, holds `follow|execute|do|run|carry out` followed within three words by `it|its steps|its instructions|the steps|every task|all tasks`. The 200-char window is a slice plus one plain regex, never a per-character lookahead. The follow phrase does not count when a negation word sits between the verb and its object, or within four words before the verb in the same clause, so `Read skills/work/SKILL.md and do not perform all tasks` stays allowed.

#### Feature: Per-task scoping

- **Description**: Let a per-task prompt mention a phase.
- **Inputs**: the field (prompt or description) that holds the match. Scoping in the other field does not count, so `description: "Run plan-tasks for PRD 00300"` beside a task-3 prompt stays refused (today's tests).
- **Outputs**: scoped or not.
- **Behavior**: The field is scoped when it names exactly one distinct task id (`\btasks?\s+#?([A-Z]?\d+)\b`) and no id is in range form (preceded by `from|after|starting at|starting with`, or followed by `onward(s)|through|to|until|and on|and later|, <digit>|and <digit>|-<digit>|..`), or when it names exactly one distinct path token (`\S*/\S+\.\w+`) that is not under `prds/` and not a `SKILL.md`. A free `only` does not scope: all four real 00242 delegations carry one (measured with `rg`, 2026-10-10), and `resume-work-agent.txt` names tasks 1, 2 and 7.

#### Feature: Bound negation

- **Description**: A prohibition is not a delegation.
- **Inputs**: field text and the match start.
- **Outputs**: negated or not.
- **Behavior**: A match is negated only when a negation word from today's `_NEGATION` set sits in the same clause with at most four words between it and the phase name. Today's double-negation exception stays: `not|never|does not|doesn't|don't|won't` directly followed by `hesitate|fail|only` does not negate. The 20-character window and `_NO_NEGATION` per-character lookahead go away. "This is not optional: run the work phase", "Do not stop - run the work phase" and "Don't stop: run the work phase." are refused; "Do not run the work phase for PRD 7." and "Code review isn't only running the work phase" are allowed.

### Capability: Dispatch policy

#### Feature: Exemptions

- **Description**: Types that never delegate are not checked.
- **Inputs**: `tool_input["subagent_type"]`.
- **Outputs**: exempt or checked.
- **Behavior**: Today's 13 `autopilot:` read-only reviewers stay exempt. Any type starting with `agoge:` is exempt (Read and Bash only, no Skill tool). `agoge`, `walter`, `agoge-walter` and `xagoge:walter` are still checked. An unhashable type fails open as today.

#### Feature: Deny message per subagent type

- **Description**: Tell the session which words matched and what to do.
- **Inputs**: the match, `subagent_type`.
- **Outputs**: stderr text, exit 2.
- **Behavior**: `span = " ".join(text[max(0, start - 10):start + 20].split())` where `start` is the phase name's offset. Per-task personas (`autopilot:ivan`, `autopilot:tess`, `autopilot:devon`, any `autopilot:worker-*`) get: `autopilot: this per-task prompt names a phase as the thing to run: "<span>". If it only mentions the phase, rephrase that sentence or scope it to one task (task N). hooks/guard_phase_delegation.py denied this Agent call.` Everyone else gets today's text plus the quote: `autopilot: run the phase skill (plan-tasks / design-solution / work) with the Skill tool in THIS session; dispatch Agent calls only for per-task subagents (Ivan, Tess, Devon, reviewers). Matched: "<span>". hooks/guard_phase_delegation.py denied this Agent call.`

### Capability: Hook input hardening

#### Feature: Six-hook stdin matrix

- **Description**: Pin how every stdin-reading hook treats bad input.
- **Inputs**: invalid UTF-8 (`b"\xff\xfe\x80"`), deep nesting (`"[" * 100000 + "]" * 100000`), empty stdin, and a valid payload whose strings hold U+FFFD.
- **Outputs**: exit code and stderr per hook and case.
- **Behavior**: `enforce_prd_location.py`, `guard_push_on_critical.py`, `guard_skill_after_leave.py`, `guard_phase_delegation.py`, `note_session_leave.py` and `guard_stop_on_live_lanes.py` each exit 0 with no `Traceback` on every case, run as subprocesses under `_AUTOPILOT_LOOP=1` and `PYTHONIOENCODING=utf-8:strict`, cwd a `tmp_path`.

#### Feature: Lone surrogate in a PRD path

- **Description**: `enforce_prd_location.py` must not fail open on `\ud800`.
- **Inputs**: a Write whose `file_path` is `<repo>/backlog/x\ud800.md`.
- **Outputs**: exit 2 with the lifecycle block message.
- **Behavior**: `_check_file_path` first sets `file_path = file_path.encode("utf-8", "replace").decode("utf-8")`, before `Path.resolve()` and the layout check.

#### Feature: Replaced byte in a session id

- **Description**: Two ids that differ only in an invalid byte must not share a leave marker (report 2, finding 21).
- **Inputs**: `payload["session_id"]` holding U+FFFD.
- **Outputs**: `note_session_leave.py` writes no marker; `guard_skill_after_leave.py` allows.
- **Behavior**: both hooks treat a session id containing `"�"` like a missing one: `allow()` before any marker read or write.

### Capability: Replay acceptance

#### Feature: Committed replay fixture

- **Description**: The hardest real dispatches, frozen in the repo.
- **Inputs**: Agent `tool_use` records from `~/.claude/projects/-Users-bob-git-src-github-com-buvis-claude-autopilot/**/*.jsonl`.
- **Outputs**: `hooks/fixtures/phase_delegation/replay.jsonl`, one JSON object per line: `{"id", "source", "expect": "allow"|"deny", "tool_input": {"description", "prompt", "subagent_type"}}` (other `tool_input` keys dropped).
- **Behavior**: `expect: deny` for the four 00242 delegations: `toolu_011eQouP7ZMWxba7b8ijXmiR`, `toolu_01WwjmFapBm8w3NYCwWddUbk`, `toolu_01S6V4tZDtrS3ePnXWtD9dT2`, `toolu_01Ku4TbcQoeik6ZLf5XkkAuD`. `expect: allow` for the 13 dispatches HEAD refuses today that the operator wants passed: agoge `toolu_01W15m4SvfMuFzYgJ6hM5Y86`, `toolu_012Gh9qVJu1j2rxWESvHbnep`, `toolu_01XtemYTu4cTr5DJWXsiC81R`, `toolu_01M5oN1rSytcoYhttzuwNnsr`, `toolu_016VpY14R3QFzMz6yKVBq4Tj`, `toolu_01CFhHJX1aJZENkuUDCBBfXd`, `toolu_01CNBVNKXWXz5Z6CcDK4iaYE`, `toolu_01XHa3WeqZ6jCuKGKvwD8Xcm`, `toolu_01BLKioUGyrQbNRkVYhMdgyA`; task-6 Tess/Ivan `toolu_014mbSK3XoKao3BMuULjckE8`, `toolu_01Mn6rkcnB3WWen3LjbfYTL5`, `toolu_01H6yng3GUc8dFhzCeGdc1j6`; worker-opus Ivan `toolu_01V199BvGGdSG4pvZ4B9Y1sT`. The general-purpose "Adversarial review of design doc draft" (`toolu_01F71bwTZ8FNSnRRt2rDxZiQ`) is neither per-task nor a reviewer persona; it is left out and the full replay reports it under `other`. The `docs/dev/tmp/dispatch-*.txt` files that name `guard_phase_delegation` stay out: their content reached the subagent from disk, and the Agent call carried only a "read this file" pointer, so the guard never saw it.

#### Feature: Full local replay

- **Description**: Replay every real dispatch this machine holds.
- **Inputs**: `--transcripts DIR` (default `~/.claude/projects/<repo root with / and . replaced by ->`), `--guard PATH` (default `hooks/guard_phase_delegation.py`).
- **Outputs**: stdout lines `total N`, then per bucket `<bucket> <count> refused <n>`, then one line per refusal `<bucket> <id> <subagent_type> <description>`; exit code.
- **Behavior**: read-only. Extract unique Agent `tool_input`s (dedupe on `json.dumps(ti, sort_keys=True)`), run `is_phase_delegation`. Buckets: `agoge` (`agoge:*`), `reviewer` (the guard's exempt `autopilot:` set), `per-task` (`autopilot:ivan|tess|devon|worker-*`, or `general-purpose`/missing type whose description matches `(?i)\b(ivan|tess|devon)\b|\btask\s+[A-Z]?\d+\b`), else `other`. Exit 2 when DIR is missing or holds zero Agent inputs; exit 1 when any `per-task`, `agoge` or `reviewer` record is refused or any of the four deny ids is present and allowed; else exit 0. `other` refusals are printed, never fail. The corpus size drifts as transcripts rotate (1,112 for walter, 1,082 on 2026-10-10), so no count is asserted.

### Capability: Release truth

#### Feature: CHANGELOG line for v2

- **Description**: Replace the 00267 guard line in `[Unreleased]`.
- **Inputs**: `CHANGELOG.md` line starting `- **hooks**: the phase-delegation guard now catches`.
- **Outputs**: three lines under `### Fixed`.
- **Behavior**: replace that line with exactly these three lines:

```markdown
- **hooks**: the phase-delegation guard checks sentence shape instead of word lists: in loop mode it refuses an Agent call whose prompt or description names a phase or phase skill as the thing to run (followed by a PRD, a task range, a whole-run phrase or the end of its clause) unless that same field scopes it to one task or one named file; a prompt that starts with `/autopilot:work`, `/autopilot:plan-tasks` or `/autopilot:design-solution` is always refused, a negation counts only inside its own clause, format characters and combining marks are stripped and every dash reads as `-`, `agoge:` personas are exempt like the read-only reviewers, and the refusal quotes the matched words and tells a per-task persona to rephrase that sentence
- **hooks**: `enforce_prd_location` refuses a repo-root `backlog/` write whose path holds a lone surrogate instead of failing open
- **hooks**: the leave-marker hooks ignore a session id that holds a replaced invalid byte (U+FFFD), so two sessions can no longer share one leave marker
```

## Structural Decomposition

### Repository Structure

```
claude-autopilot/
├── CHANGELOG.md                                   # Maps to: CHANGELOG line for v2 (task 10)
├── dev/
│   └── bin/
│       ├── release-checks                         # gate entries for every new test file (tasks 2-9)
│       ├── replay_delegation_guard.py             # NEW. Maps to: Full local replay (task 9)
│       └── test_replay_delegation_guard.py        # NEW. Full local replay tests (task 9)
└── hooks/
    ├── guard_phase_delegation.py                  # Maps to: Structural delegation check, Dispatch policy (tasks 1, 5, 6, 7)
    ├── enforce_prd_location.py                    # Maps to: Lone surrogate in a PRD path (task 3)
    ├── note_session_leave.py                      # Maps to: Replaced byte in a session id (task 4)
    ├── guard_skill_after_leave.py                 # Maps to: Replaced byte in a session id (task 4)
    ├── test_guard_phase_delegation.py             # existing; must stay green, edit only an assertion v2 makes false (task 5)
    ├── test_guard_phase_delegation_narrowing.py   # existing; v1-mechanics cases re-sorted (task 5)
    ├── test_guard_phase_delegation_structure.py   # NEW. predicate tests (tasks 1, 5)
    ├── test_guard_phase_delegation_dispatch.py    # NEW. exemptions, messages, timing (tasks 6, 7)
    ├── test_guard_phase_delegation_replay.py      # NEW. committed replay fixture (task 2)
    ├── test_read_input.py                         # NEW. six-hook stdin matrix (task 8)
    ├── test_enforce_prd_location.py               # existing; surrogate test (task 3)
    ├── test_guard_skill_after_leave.py            # existing; U+FFFD session tests (task 4)
    └── fixtures/
        └── phase_delegation/
            └── replay.jsonl                       # NEW. Maps to: Committed replay fixture (task 2)
```

No other file changes. `hooks/hooks.json`, `hooks/_common.py` and `hooks/fixtures/phase_delegation/{allowed,denied}/` stay as they are; must-deny and must-allow cases live as escaped strings in the new test modules, so invisible code points survive editors.

### Module: guard_phase_delegation

- **Maps to capability**: Structural delegation check, Dispatch policy
- **Responsibility**: refuse whole-phase delegation to a subagent in loop mode, and say why
- **Exports**:
  - `is_phase_delegation(tool_input: dict) -> bool` - signature unchanged
  - `find_phase_delegation(tool_input: dict) -> str | None` - new; the quoted span of the first counting match, or None
  - `_normalize(text: str) -> str` - module-private, imported by tests
  - `_READ_ONLY_REVIEWERS` - unchanged frozenset; `agoge:` exemption is a prefix check beside it

### Module: leave-marker hooks

- **Maps to capability**: Hook input hardening (replaced byte in a session id)
- **Responsibility**: `note_session_leave.py` and `guard_skill_after_leave.py` fail open on a U+FFFD session id
- **Exports**: none new

### Module: enforce_prd_location

- **Maps to capability**: Hook input hardening (lone surrogate)
- **Responsibility**: normalize the path before resolving it
- **Exports**: none new

### Module: replay_delegation_guard

- **Maps to capability**: Replay acceptance
- **Responsibility**: read-only replay of local transcript dispatches through the guard
- **Exports**: `main(argv: list[str] | None = None) -> int`, `bucket(tool_input: dict, exempt: frozenset[str]) -> str`

### Module: gate and docs

- **Maps to capability**: Release truth
- **Responsibility**: `dev/bin/release-checks` runs every new test file; `CHANGELOG.md` states v2's real behavior
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **guard_phase_delegation (normalization)**: `_normalize`, used by the predicate
- **replay fixture**: `replay.jsonl`, the predicate's real-data target
- **enforce_prd_location**: independent fix
- **leave-marker hooks**: independent fix

### Core Layer (Phase 1)
- **guard_phase_delegation (predicate)**: Depends on [guard_phase_delegation (normalization), replay fixture]
- **guard_phase_delegation (dispatch policy, timing)**: Depends on [guard_phase_delegation (predicate)]

### Integration Layer (Phase 2)
- **test_read_input**: Depends on [leave-marker hooks, enforce_prd_location, guard_phase_delegation (dispatch policy)]
- **replay_delegation_guard**: Depends on [guard_phase_delegation (dispatch policy)]
- **gate and docs**: Depends on [every module above]

## Implementation Phases

Every task that adds a `hooks/test_*.py` or `dev/bin/test_*.py` file adds it to `dev/bin/release-checks` in the same task (hook files in the `[checks] hook registration` block), or `test_hook_registration.py::test_every_hooks_test_file_is_in_the_release_gate` goes red.

### Phase 0: Foundation
**Goal**: normalization, the frozen real-data target, and the two small hook fixes.

**Tasks**:
- [ ] 1. Normalization: add `_normalize` per the Normalization feature and call it on each field in `is_phase_delegation` (replaces today's `_INVISIBLE` translate and plain NFKC) (no deps) - Acceptance: new `hooks/test_guard_phase_delegation_structure.py::test_lookalike_dashes_and_invisible_marks_are_normalized_and_denied`, parametrized over `"Invoke /autopilot:plan‑tasks for PRD 00300."`, `"Invoke /autopilot:plan−tasks for PRD 00300."`, `"Run the wo﻿rk phase for PRD 00300."`, `"Run the wo⁡rk phase for PRD 00300."`, `"Run the wo᠎rk phase for PRD 00300."`, `"Run the wórk phase for PRD 00300."`, `"Run the wo͏rk phase for PRD 00300."`, all `True`; fails at base on every case (2026-10-07 report: 0/0).
- [ ] 2. Replay fixture: write `hooks/fixtures/phase_delegation/replay.jsonl` from the transcripts with the 17 ids and labels in the Committed replay fixture feature. Premise: each id is still in `~/.claude/projects/-Users-bob-git-src-github-com-buvis-claude-autopilot/`; re-check at execution with `rg -l <id>` on that tree, and skip and report any missing id, never invent a record. Add `hooks/test_guard_phase_delegation_replay.py` (no deps) - Acceptance: `test_replay_fixture_holds_the_four_real_delegations` (all four deny ids present) and `test_every_captured_real_dispatch_gets_its_expected_verdict` (subprocess per record under `_AUTOPILOT_LOOP=1`; deny records exit 2, allow records exit 0) pass after task 6; the verdict test fails at base on the 13 allow records.
- [ ] 3. Lone surrogate: normalize `file_path` in `enforce_prd_location._check_file_path` per the feature (no deps) - Acceptance: new `hooks/test_enforce_prd_location.py::LayoutVocabularyTest::test_blocks_repo_root_backlog_write_whose_path_holds_a_lone_surrogate` (`run()` with `file_path = str(_REPO_ROOT / "backlog" / "x\ud800.md")` returns exit 2 and the lifecycle message) passes; fails at base (exit 0, "policy hook degraded").
- [ ] 4. Session id with U+FFFD: both leave-marker hooks `allow()` on a session id holding `"�"` (no deps) - Acceptance: new `hooks/test_guard_skill_after_leave.py::test_leave_row_with_a_replaced_byte_session_writes_nothing` and `::test_skill_call_with_a_replaced_byte_session_passes_despite_a_matching_marker` (marker `{"session": "s1�"}`, Skill call from `s1�` exits 0) pass; the second fails at base (exit 2).

**Exit Criteria**: tasks 1, 3, 4 tests pass; the replay fixture holds every id the premise check found.

### Phase 1: Core
**Goal**: the v2 predicate, its dispatch policy and its cost bound.

**Tasks**:
- [ ] 5. Structural predicate: replace `_COLON_VERBS`, `_WIDENED_VERBS`, `_IMPERATIVE`, `_GAP_WORD`, `_GAP`, `_NOT_COMPOUND`, `_NO_NEGATION`, `_SKILL_READ`, `_DELEGATION_PATTERNS` and `_negated_before` with the object-position, bare-prompt, SKILL.md, scoping and bound-negation features; add `find_phase_delegation`. Every regex runs in linear time (no nested or per-character lookahead quantifiers) (depends on: 1, 2) - Acceptance, all in `hooks/test_guard_phase_delegation_structure.py`, each failing at base where marked:
  - `test_packet_three_phrasings_are_denied` (fails at base): `Run your work phase for PRD 00300 now.`, `Run our work phase for PRD 00300.`, `Run its work phase for PRD 00300.`, `Run the next work phase for PRD 00300.`, `Run all of the work phase for PRD 00300.`, `Kick off the work phase for PRD 00300 and finish every task.`, `Begin the work phase for PRD 00300.`, `Proceed with the work phase for PRD 00300.`, `Finish the work phase for PRD 00300.`, `Go through the work phase for PRD 00300.`, `Carry out the work phase for PRD 00300.`, `Run the work-phase for PRD 00300.`, `Run the **work phase** for PRD 00300.`, `Run “/autopilot:work” now.`, `Run «/autopilot:work» now.`, `Run 「/autopilot:work」 now.`, `Please start the entire work phase for PRD 00300 now.`
  - `test_bare_slash_command_prompt_is_always_denied` (fails at base): `/autopilot:work docs/dev/project-management/prds/wip/00300.md`, `/autopilot:plan-tasks 00300 task 3 only`
  - `test_skill_md_read_via_any_path_prefix_is_denied` (fails at base): `Read /Users/bob/.claude/plugins/cache/buvis-plugins/autopilot/0.9.0/skills/work/SKILL.md and follow it for every task.`, `Read ${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md and execute its steps for PRD 00300.`
  - `test_emphatic_negation_before_a_colon_or_dash_is_denied` (fails at base): `This is not optional: run the work phase for PRD 00300.`, `Do not stop - run the work phase for PRD 00300.`, `Don't stop: run the work phase.`
  - `test_compound_noun_cover_with_a_whole_run_marker_is_denied` (fails at base): `Start the work phase review of PRD 00300, then keep going through every task until done.`, `Work phase for PRD 00300: start it now.`
  - `test_per_task_prompts_that_mention_a_phase_are_allowed` (fails at base), `subagent_type: autopilot:ivan`: `Complete the planning phase notes in docs/dev/project-management/plans/00300.md; task 3 only.`, `Call the plan-tasks helper script with --dry-run`, `Do design-solution/references/x.md first`, `Do the work phase tests pass on this branch?`, `Do the work phase handoff test`, `Call the work phase helper`, `Start the design phase doc review`, `Launch the work phase timer test`, and ``Quote this line verbatim: …every `task-add` call `/autopilot:plan-tasks` made…``
  - `test_one_named_task_or_file_scopes_a_phase_mention` (allowed, fails at base): `Update hooks/guard.py so it can run the work phase.`, `For task 3, make the hook run the work phase.`
  - `test_task_ranges_prd_paths_and_a_free_only_do_not_scope` (denied): `Run the work phase for PRD 7 from task 2 onward.`, `Run the work phase for PRD 7, tasks 1 and 2.`, `Run the work phase for docs/dev/project-management/prds/wip/00300.md.`, `Run the work phase for PRD 7; use only the repo tools.`
  - `test_per_task_personas_count_only_the_strong_anchor` (allowed, `autopilot:worker-opus`, fails at base): ``Insert one sentence before the line "Invoke `/autopilot:work` skill. It runs until all tasks complete."``; denied for the same persona: `Run "/autopilot:work" for PRD 7.`
  - `test_quoted_text_is_still_checked` (denied, `general-purpose`): `"Run the work phase for PRD 7."` and ``Insert the line "Invoke `/autopilot:work` skill."`` (the weak anchor still counts for non-per-task agents, quotes or not)
  - `test_prepositional_and_question_mentions_are_allowed`: `Tasks complete in the work phase`, `In the work phase: do not skip tests`, `Decide what to do about the work phase`, `Work phase: complete`, `Did you run the work phase?`
  - `test_a_negation_binds_only_inside_its_clause`: allowed `Do not run the work phase for PRD 7.`, `Never fail to report; do not run the work phase.`, `Code review isn't only running the work phase`; denied `Do not wait for me. Run the work phase for PRD 7.`, `Do not, under any circumstances, run the work phase.`
  Narrowing re-sort, premise `rg -c "^def test_" hooks/test_guard_phase_delegation_narrowing.py` is `14` (re-check at execution; on a different count skip the re-sort and report): flip to `True` the cases `run-four-gap-words`, `start-four-gap-words`, `skill-four-gap-words` (rename the test `test_gap_words_no_longer_have_a_limit`), `Run the entire plan-tasks skill` and `Run the full test suite before touching plan-tasks` (rename `test_bare_skill_name_at_the_end_of_a_clause_is_denied`), and `Start reviewing the design phase` (move it to a new denied parametrization); flip `test_compound_noun_head_does_not_excuse_an_original_verb` to `False` and rename it `test_a_phase_named_before_a_compound_head_is_allowed`. Every other narrowing case keeps its verdict. `hooks/test_guard_phase_delegation.py` passes unchanged; if one of its assertions contradicts a feature above, change only that assertion and name it in the task report.
- [ ] 6. Dispatch policy: `agoge:` prefix exemption and the per-type deny message with the span (depends on: 5) - Acceptance, new `hooks/test_guard_phase_delegation_dispatch.py`: every case uses the prompt `Run the work phase for PRD 00300.`; `test_agoge_personas_are_exempt` (`agoge:walter|wendy|trudy|heidi|peggy|olivia|judy` exit 0; fails at base), `test_agoge_lookalike_types_are_still_checked` (`agoge`, `walter`, `agoge-walter`, `xagoge:walter` exit 2), `test_per_task_persona_refusal_says_rephrase_and_quotes_the_match` (`autopilot:ivan|tess|devon|worker-sonnet|worker-opus`: stderr holds `rephrase that sentence`, `Matched` absent, `"Run the work phase for PRD 0"` quoted, and the REASON line; fails at base), `test_other_refusals_keep_the_skill_tool_text_and_quote_the_match` (`general-purpose`, `Explore`, no type: stderr holds `with the Skill tool in THIS session` and `Matched: "Run the work phase for PRD 0"`; fails at base). Then `hooks/test_guard_phase_delegation_replay.py` passes in full.
- [ ] 7. Cost bound: (depends on: 5) - Acceptance: new `hooks/test_guard_phase_delegation_dispatch.py::test_guard_time_per_mb_stays_under_the_baseline` builds two 1 MB prompts (`"Read work/SKILL.md " + "not " * 262144`, and `"run the the the " * 65536`), takes the best of three `time.perf_counter()` runs of `is_phase_delegation` each, prints `guard s/MB crafted=<x> prose=<y>`, and asserts each is under 0.3 s; fails at base (crafted about 0.64 s/MB, report 1 finding 12).

**Exit Criteria**: the structure, dispatch, replay and narrowing test files pass.

### Phase 2: Integration
**Goal**: pin all six stdin hooks, replay the real corpus, and make the gate and CHANGELOG true.

**Tasks**:
- [ ] 8. Six-hook stdin matrix: new `hooks/test_read_input.py` per the feature (depends on: 3, 4, 6) - Acceptance: `test_every_stdin_hook_survives_bad_input` parametrized over 6 hooks x 4 cases (exit 0, no `Traceback`) and `test_replaced_bytes_inside_a_string_are_still_checked` (the guard payload with `\xff` inside a string value still exits 2) pass. These pin 00267 behavior and pass at base except the U+FFFD case for `guard_skill_after_leave.py` with a matching marker, which task 4 fixed; say so in the task report.
- [ ] 9. Full local replay: `dev/bin/replay_delegation_guard.py` per the feature, plus `dev/bin/test_replay_delegation_guard.py` (depends on: 6) - Acceptance: `test_buckets_follow_subagent_type_and_description`, `test_refused_per_task_record_exits_one`, `test_allowed_known_delegation_exits_one`, `test_missing_or_empty_transcript_dir_exits_two`, `test_other_refusals_are_printed_but_exit_zero` pass on synthetic transcript dirs under `tmp_path` (all fail at base: the script does not exist). Then run `python3 dev/bin/replay_delegation_guard.py` once and paste its full stdout and exit code into the task report: exit 0 is required. If it exits 1, fix the predicate, never the buckets or the deny-id list.
- [ ] 10. CHANGELOG: replace the 00267 guard line with the three lines in the CHANGELOG feature (depends on: 5, 6, 3, 4) - Acceptance: `rg -c "ordinary prose about a phase stays allowed|up to three determiner words|zero-width characters" CHANGELOG.md` prints nothing (exit 1), and `rg -c "checks sentence shape instead of word lists" CHANGELOG.md` prints `1`.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0, and `python3 dev/bin/replay_delegation_guard.py` exits 0 on this machine.

## Test Strategy

### Critical Scenarios
- **Happy path**: a real 00242 delegation ("You are executing the `autopilot:design-solution` skill for PRD ...") → Expected: exit 2, today's text plus `Matched: "..."`.
- **Happy path**: a real per-task Ivan or worker dispatch that mentions a phase → Expected: exit 0.
- **Edge case**: a per-task persona quoting a skill line it must insert (weak anchor only) → Expected: allowed; the same persona asked to `Run "/autopilot:work" for PRD 7` (strong anchor) → Expected: refused; a general-purpose agent sent a quoted delegation sentence → Expected: refused.
- **Edge case**: a free `only` or `task 1 onward` beside a phase hand-over → Expected: refused (not scoping).
- **Edge case**: `agoge:walter` quoting `Run the work phase for PRD 00300` → Expected: exit 0.
- **Error case**: invalid UTF-8, deep nesting, empty stdin, U+FFFD session id → Expected: every hook exits 0 with no traceback; leave hooks ignore the id.
- **Error case**: lone surrogate in a repo-root `backlog/` path → Expected: exit 2.
- **Cost**: 1 MB crafted prompt → Expected: under 0.3 s.

## Risks

- **v2 refuses real per-task prompts the fixtures miss**: the weak anchor (phase name at clause end) is new surface. Mitigation: task 9 replays every local dispatch and exits 1 on any per-task refusal; the fix goes in the predicate, and the rework loop carries it.
- **Per-task personas skip the weak anchor**: a per-task prompt that hands over a phase with no PRD, task range or whole-run phrase (`Ivan, run the work phase.`) passes. Accepted (operator, 2026-10-10) over a quote exemption, which would open the evasion for every agent type; per-task personas are dispatched one task at a time by the work skill, so a bare phase hand-over to them is the least likely drift.
- **Committed replay fixture holds real prompts in a public repo**: the records are lane and task instructions about this repo, the same kind `hooks/fixtures/phase_delegation/allowed/` already commits verbatim. Drop any record that holds a secret-looking token; the premise check reports it.
- **Timing test is noisy under the 4-worker gate**: best of three runs and a bound about 2x above the 0.9.0 cost keep it stable; a flake means the bound, not the code, needs review.
- **Transcripts rotate**: the full replay asserts no count, and task 2 skips and reports any id that is gone.
