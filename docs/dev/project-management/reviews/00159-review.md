# Review minutes: PRD 00159 — Trim per-task review for test-only diffs

Session 1 of the fast-track drain (`dev/local/plans/00159-fast-track-backlog-drain.md`).
Reviewed 2026-08-27/28. Diff range `2be1367..a978bd6`, reworked to `c4c3034`.

## Panel

Four lenses, four fresh contexts, three model families. All four returned.

| Lens | Model | Verdict |
|------|-------|---------|
| Alice (implementation-aware consensus) | Sonnet | No CRITICAL/HIGH/MEDIUM. 3 LOW. Re-ran every acceptance command independently. |
| Blake (blind, PRD-only, never saw the diff) | Sonnet | 14 of 15 self-derived rules pass. One fail: stale SKILL.md prose. |
| Eve (doubt + de-slop) | Fable | 6 FIX, 1 VERIFY, 5 KNOWN. |
| Bob (consensus + doubt rubric, static-only) | codex | 3 Medium, 1 Low. Rubric R1/R4/R7/R9/R10 fail (static-only; cannot execute). |

Blake and Eve independently found the same stale-prose defect. That is the one
consensus finding of the cycle.

## Applied

| # | Severity | Finding | Found by | Fix |
|---|----------|---------|----------|-----|
| 1 | MEDIUM | `--tools LIST` as two argv tokens swallows the prompt: `claude --tools` is variadic (`<tools...>`). The whole tool-less-Pat capability was dead on arrival. | Eve (VERIFY item, escalated on execution) | `2436b55` — emit `--tools=LIST` as one token. Verified live both ways. |
| 2 | MEDIUM | `parse_review.py` dropped `- MEDIUM \| ...`, `**MEDIUM** \| ...`, `1. MEDIUM \| ...` as prose, exit 0, whenever a plain finding sat beside it. | Eve (verified by execution) | `bd28cde` — strip list markers and emphasis for recognition; 7 regression tests. |
| 3 | MEDIUM | `CONTRACT_CORRECTION` text carries backticks and was passed via `--set`; Bash would execute them and strip the line shapes the correction teaches. | Eve | `bd28cde` — write to a file, pass `--set-file`. Matches the rule the skill already pins for task prose. |
| 4 | MEDIUM | Step 5.7 renders the verification file at item 2, but only item 3 said to write it. A literal first run exits non-zero from `render_prompt.py`. | Eve | `bd28cde` — item 1 writes it first. |
| 5 | MEDIUM | SKILL.md:284 and `attempt-logging.md`:58 still claimed "Pat's step-5.7 review still runs for test-only tasks" — false outside rework, and it contradicts the stamp this PRD's own success metric expects. | **Blake and Eve, independently** | `bd28cde` — both reworded. |
| 6 | MEDIUM | SKILL.md:268 still called step 5.7's `BASE_SHA` a reader of `<test_commit_sha>`, contradicting line 422 and `gate-failure.md`. | Eve | `bd28cde` — reworded to one reader. |
| 7 | LOW | Step 5.7's "every tier takes it" read as overriding the `haiku` row above it. | Bob | `bd28cde` — names the haiku exit explicitly. |
| 8 | LOW | Case-insensitive `CLOSURE` matching went beyond the PRD text with no test. | Alice | `bd28cde` — regression test added. |
| 9 | LOW | `InvalidReview` stored `.reason`/`.line` that nothing read. | Eve (de-slop) | `bd28cde` — dropped, formatted message kept. |

Finding 1 is the one that mattered. Four reviewers and a green 2104-test suite
all passed over it, because the only test of that flag asserted on a **stubbed**
`claude`'s argv: the flag was present and correct, and the prompt was gone. Eve
asked for a live run; the live run failed immediately. The test now also asserts
the prompt survives as its own token.

## Declined

| Finding | Found by | Why |
|---------|----------|-----|
| Parser accepts `MEDIUM \|  \| issue \| fix` (empty fields) | Bob | Beyond the PRD's explicit validity rule (exactly four fields on ` \| `). The finding is still reported; an empty file field only misses the in-task-files gate and degrades to note-and-proceed. Not a silent loss. |
| Parser accepts `CLOSURE` outside rework context | Bob | `parse()` is a pure function over text with no rework knowledge by design. The ladder ignores closures it did not ask for. |
| `-t -f prompt.md` consumes the flag as the tools value | Bob, Eve | Every other flag in `sonnet-run.sh` (`-m`, `-d`, `-f`, `-o`) behaves the same. Fixing one in isolation is inconsistent, and the PRD specifies only the missing-value case. |
| `test_work_routing.py` is 1150 lines, over the 800 guideline | Alice | Pre-existing (>1070 before this PRD), grown only additively. Out of scope per the surgical-changes rule. |
| `is_test_path` misclassifies Django `fixtures/` seed data, OpenAPI `specs/`, ops `test_*.sh` in other repos | Eve (KNOWN) | The PRD fixes the list verbatim and its Risks section accepts the class. No such path exists in this repo — verified. |
| Prose opening with a bare severity word burns the correction retry | Eve (KNOWN) | The deliberate fail-loud side of the PRD-mandated catch. Costs one dispatch, never a silent pass. |

## Deferred — needs a home

- **`references/rework-mode.md:32`** still defines the micro-lane `BASE_SHA` as
  "the parent of the lane commit" and stamps `self_deslop: "skipped:trivial"`
  unconditionally, so a test-only micro diff stamps `trivial` rather than
  `test-only`. Found by Eve. Outside this PRD's file list; the SHA values
  coincide and no dispatch behaviour changes, so nothing is broken today. Belongs
  in a follow-up PRD.

## Deviations from the PRD as written

1. **`--tools=LIST`, not the pair `--tools <LIST>`** the PRD specifies. The
   PRD's form does not work against the real CLI (finding 1). Documented in the
   script, the tests and the CHANGELOG.
2. **CHANGELOG entries landed per commit**, not all in Phase 2 task 2, because
   the global changelog rule is blocking on every `feat` commit. Final text is
   the same and the task's acceptance check passes.
3. **The verification file's write procedure lives in `per-task-review.md`**,
   not SKILL.md. The PRD names the file but assigns the prose to no file, and
   SKILL.md had 5 lines of ceiling headroom.
4. **`CLOSURE` matched case-insensitively.** The PRD states case-insensitivity
   for severities and is silent for `CLOSURE`; matching it case-sensitively
   would silently drop a lowercase verdict. Now tested.

## Gate

- Baseline (master @ `2be1367`): **2067 passed**, 459 subtests, 53.95s
- Final (`c4c3034`): **2111 passed**, 459 subtests, 57.43s — zero failures, zero skips
- `dev/bin/release-checks`: green (112 / 5 / codex 41-0 / gemini 18-0 / sonnet 18-0)
- `skills/work/SKILL.md`: 497 lines (498 by the ceiling test's count), ceiling 500
- Live: `sonnet-run.sh -t "" -f <prompt asking to read a file>` → `NO_TOOLS_AVAILABLE`;
  the same prompt without `-t` reads the file. The PRD's "zero tool calls"
  metric is verified end to end, not inferred from help text.

Converged after one rework cycle. No CRITICAL or HIGH was open at any point.
