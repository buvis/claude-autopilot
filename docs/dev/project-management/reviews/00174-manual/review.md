# PRD 00174 — implementation and review

Implemented directly by the main agent, bypassing the autopilot loop and leaving autopilot state untouched. All eight PRD tasks are complete and the PRD is filed in `dev/local/prds/done/`. The change remains uncommitted.

## Result

- Planning and runtime admit Qwen only for exactly one implementor-writable file. Multi-file tasks retain existing Codex/Claude routing, and coupled edits stay together.
- The executable output guard rejects no-edit successes and Tess-test mutations before acceptance, restoring canonical tests only under the documented ownership checks and escalating once to Sonnet.
- Implementation commitability is checked in a temporary Git index; foreign work and the live index are preserved. Direct disk/index checks prevent Git flags from hiding test mutations.
- Routing telemetry, reports, examples, state contracts and Qwen3.8 qualification guidance agree.

## Review isolation and evidence

Three review rounds each used new subagents with `fork_turns: none`: Alice consensus, Blake blind/PRD-only, and Bob doubt/de-slop. Reviewers received their lens instructions and bounded artifacts, never the implementation-session transcript. Blake began from the original PRD and located implementation independently. The main agent alone implemented repairs; each round retained all lenses, and the final reviewers independently rechecked the last repairs in their isolated contexts.

- [Alice final review](alice-3.md): no remaining in-scope findings; 45 focused tests plus an independent bare-repository fixture.
- [Blake final review](blake-3.md): B1–B19 pass; independent ordinary/split-index fixtures.
- [Bob final doubt review](bob-3.md): D1–D5 pass; 10 candidates = 2 fixed + 8 verified, none remaining. Independent 264-test focused suite and adversarial Git fixtures passed after the second pass.
- [Round 1 repairs](rework-1.md), [round 2 repairs](rework-2.md), [round 3 repairs](rework-3.md).
- [Frozen final diff](cycle-3-final.diff) and [reviewed file hashes](final-sha256.txt).

## Validation and limits

The final full suite passed: **2563 tests, 459 subtests**, with 32 existing skips and four existing legacy-schema warnings. Required release harnesses, plugin/marketplace validation, scoped style checks and whitespace checks passed. Scoped Ruff passes with only the documented per-file exception for the preexisting render_report.py shebang/mode mismatch. [Complete validation evidence](validation.md).

Existing debt remains explicitly recorded: the oversized test_work_routing.py (Alice R13), an unchanged weak prose assertion, and the existing Ruff file-mode finding. None is an introduced or waived PRD defect. The three preexisting routing-tuner/ledger edits were preserved.

No live Qwen/Sonnet dispatch or autopilot loop was run; executable Git fixtures and model-followed call-site contracts were tested. The external multi-file qualification remains outside this PRD. No task worktree, branch or executed plan was created; temporary reproducers were removed or retained with the review evidence.
