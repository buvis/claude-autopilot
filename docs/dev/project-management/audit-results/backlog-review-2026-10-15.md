# Backlog review - claude-autopilot - 2026-10-15

Verdict: GO

Run under the standing authorization (`~/.claude/AGENTS.md` § Autonomy): findings adjudicated by the agent and applied in one pass, no per-finding walkthrough. The eight PRDs were written the same evening from the walked agoge-2026-10-15 report, the batch 202610141430 ledgers and the two parked v1 PRDs, so lens D ran while they were written (every citation re-read against HEAD 807ed12b with `rg` or `Read`); no subagent fan-out. Mechanical gates after the apply pass: `check_links.py` 0 findings under `prds/backlog` or `prds/wip`; `ground_prd.py` over the eight PRDs `{"blocking": 0, "unverified": 0}` (three rounds: 21 blocking, then 1, then 0). Law loaded from `~/.agents/skills/create-prd/SKILL.md` and `assets/minimal.md`; budget and tier rules from the installed `autopilot:plan-tasks` 0.9.0.

## Map
| # | PRD | template | lines | subsystems | depends on | verdict |
|---|---|---|---|---|---|---|
| 00320 | refuse-every-unsafe-verify-log-sink v2 | minimal | 75 | cli/__main__.py `_refuse_verify_log`, cli/verification.py `_lock_and_check`/`_run_locked_gate`, new test file | none (supersedes 00306; `lane: full`) | FIX -> READY |
| 00321 | cap-check-classifies-every-cell v2 | minimal | 76 | cli/cap_check.py, cli/triage.py `qualifies`, cli/records.py `do_stall`, phase-review.md, recovery.md | none (supersedes 00310) | FIX -> READY |
| 00322 | kill-the-gate-on-every-signal | minimal | 75 | cli/verification.py signals and lock, cli/review_stage.py `_run_script`, replay script | 00320 lands first (same file) | FIX -> READY |
| 00323 | tests-line-and-verify-record-say-red | minimal | 79 | cli/verification.py `_write_record`, cli/review_stage.py `_gate_result_line`, cli/__main__.py `_report_verify`, two docs | 00320 and 00322 first | FIX -> READY |
| 00324 | guard-pairs-delimiters-as-nested-runs | minimal | 63 | hooks/guard_phase_delegation.py and its lexicon, three hook test files | none | FIX -> READY |
| 00325 | sweep-reads-emoji-rows-by-character-class | minimal | 63 | cli/gate.py, two gate test files | none | READY |
| 00326 | close-the-loops-remaining-verb-and-ledger-truths v2 | minimal | 96 | selection, statectl, markers, loop metrics, triage, fast-track record_item, two test fixes | 00321 first (`qualifies`) | FIX -> READY |
| 00327 | release-gate-and-notes-say-what-ships v2 | minimal | 77 | dev/bin/release, dev/bin/release-checks, CHANGELOG, done PRD 00313, one test file | last (measures the gate after the others' tests land) | FIX -> READY |

Hygiene: eight `NNNNN-{slug}-v{n}.md` files, numbers unique across backlog, wip (empty), hold (empty), done (max 00319) and discovery (max 00281). The gitignored `backlog/.migration-placeholder` is not selectable.

## Findings
### Blocking
- [00321] D grounding: nine fixture File-cell examples written as backticked `path:line` tokens parsed as citations to files that do not exist, and a doubled-backtick sample desynchronised the symbol scan so every later citation on the line lost its anchor (21 gate rows) -> fails as: stall (an implementor premise check trips on the dangling pointers). Fix: the cell shapes described in words, the doubled-backtick sample removed. Applied.
- [00320] A/D: three mentions of the store's `state.json` by full path, a file the loop deletes at drain, failed `check_links.py` -> fails as: stall. Fix: described as "the store state file". Applied.
- [00327] A: the renamed test `test_skip_ceiling_fails_the_gate_above_the_ceiling` was not declared under `New symbols:` -> fails as: wrong-TDD lock-in (the planner invents a name). Fix: declared. Applied.

### Non-blocking
- [00322, 00323, 00326] E cross-invalidation: 00320 adds a function to `verification.py` and 00320-00323 all edit `_run_verify`, 00321 adds a branch to `qualifies` that 00326 also edits, so the later PRDs' line numbers are stale by construction. Fix: one Source sentence in each naming HEAD 807ed12b and stating that symbols anchor; CHANGELOG lines identified by quoted text. Applied.
- [00322] B resource sanity: the SIGINT storm test at 300 trials would add about a minute to every gate run (the very cost packet 12 measures). Fix: 100 trials, bounded at 20 s. Applied.
- [00320] B: `lane: full` is honoured by the installed 0.9.0 (`lane.py` reads `declared.get("lane")`); without it the card-sized PRD would route to the fast-track lane again, whose one rework left v1's CRITICAL standing. No edit; noted so nobody removes the field as unrecognised.
- [00324] B: the mutation-style test (`test_backtick_exclusion_in_cite_boundary_can_fail`) replaces a module regex at runtime; acceptable, it is the only way to prove the exclusion is load-bearing. No edit.
- [00327] B: the live MCP step in `dev/bin/release` makes a real `claude` call at release time; the fixture tests stub `uv` on PATH, so the gate never pays it. No edit.
- [all] A: `model_tier_rationale` is not in this gate's recognised-field list but is in create-prd's (ignored by both parsers). No edit.

### Questions
- None. Every contract a test author needs carries its exact expression; the one judgment left open in the agoge packets (00321 packet 3: exit 2 or stall on an unreadable cell) is decided in the PRD (stall).

## Reshapes
- None. 00326 spans six modules but each is a few lines with its own test; plan-tasks splits it at file boundaries into two Phase 1 tasks as written.

## Gaps
- Test mass and gate time: 00327 restates 00313's 240 s line against the measurement instead of parallelising the `review verbs` block; the parallel-safety proof for that block is an `/assess-evolution` candidate after this batch.
- Outside the repo: engram's readonly index under the seatbelt (every review's findings pack fails), the dotfiles commit of `communication.md`, and the agoge pack's `allocate_prd_number.py` still scanning `dev/local/prds/`.

## End state after this batch
`autopilot verify` refuses every sink it should (by identity, with an exclusive open), survives every catchable signal without leaving a gate or a lock behind, and the `Tests:` line reviewers read is red whenever the gate was. `cap-check` reads every cell, proves its range, stalls on what it cannot read, and a `cap_regression` park leaves a ledger record and a stub. The delegation guard closes its five measured bypasses and keeps its linear budget; the findings sweep reads rows by character class. The loop's small verbs are discoverable and bounded to their store, the session ledger names the right PRD, stubs are minted only for open work, and the release script refuses on a CRITICAL stub and runs the live MCP test itself. Still half-finished after it: the gate's five-minute wall, `__main__.py`'s length, and the sandbox-side engram index.

## Frontmatter tuning
| PRD | suggestion | why |
|---|---|---|
| 00320, 00321, 00322, 00324 | keep `opus`, `design: run` | a write boundary, a classifier with measured fail-open shapes, signal races, pairing semantics |
| 00323, 00325, 00326, 00327 | keep `sonnet`, `design: skip` | exact expressions and named fail-first tests |

## Decisions applied
- 00321: fixture cells in words, doubled-backtick sample removed, `beef` unbackticked (Blocking, applied).
- 00320: store state file named without its path (Blocking, applied).
- 00327: renamed test declared (Blocking, applied).
- 00322, 00323, 00326: HEAD and symbol-anchor sentence under Source; 00322 storm trials 300 -> 100 (applied).
- Lens A re-run on the touched PRDs: headings unchanged, every task line keeps its `Acceptance:` clause; `ground_prd.py` after the pass: `{"blocking": 0, "unverified": 0}`.

Final verdict: GO. Drain order 00320, 00321, 00322, 00323, 00324, 00325, 00326, 00327. 00320 and 00324 are release blockers (destructive `verify --log`; four guard regressions against 0.9.0); the release waits for the batch.
