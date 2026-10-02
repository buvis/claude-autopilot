# Review: PRD 00166 — check split hygiene in touched test files

Session 5 of the 00159-00168 fast-track drain. Base `89bbfd2`, head `f3579f9`.
Two review cycles, converged. Suite 2129 → **2159 passed, 4 warnings, 459
subtests, 0 failures, 0 skips**.

## Panel

| Lens | Who | Cycle 1 | Cycle 2 |
|---|---|---|---|
| Consensus, implementation-aware | Alice (Sonnet) | 1 CRITICAL | 1 MEDIUM, 1 LOW, R1-R13 all pass |
| Blind, PRD-only | Blake (Sonnet) | 1 HIGH | 1 HIGH, 1 LOW |
| Doubt + de-slop | Eve (Fable) | 4 FIX, 1 VERIFY, 3 KNOWN | 2 FIX, 4 KNOWN, D1-D5 pass |
| Consensus, codex, static-only | Bob (codex) | dispatch failed | 8 findings, R-verdicts mixed |
| Adversarial verifier | Victor | — | 1 REFUTED |

Bob's first two dispatches failed. Session 4's note said to stage his inputs
under `dev/local/tmp/` because the codex sandbox is workspace-scoped; that was
necessary but not sufficient. His persona says "Do NOT attempt to run commands",
and in the codex CLI the only file reader IS a command, so he answered "no
non-command workspace file reader is available" and failed every rubric rule.
The fix is the one the plan already specifies and I had not followed: **inline
the file contents into his prompt** rather than referencing paths. An 81KB
prompt carrying context + diff + PRD produced a full, useful review.

## The live check found what four reviewers and 2146 green tests did not

The plan's S1 rule ("run the live check the tests cannot") earned its place
before the panel even reported. Running the new checker against this repo's own
test corpus flagged `from __future__ import annotations` in **14 of 14**
`skills/work/scripts/test_*.py` files. `annotations` is bound and never loaded,
so the plain rule called it dead — and the deletion-only fixer it feeds would
have stripped the directive repo-wide, silently un-lazying every annotation.
The whole suite was green while that was live. Fixed in `9b4318c`.

That single result reframed the review: the UNUSED rule's false-positive class
was real and not exhausted, which is what the panel then went hunting.

## Findings

Deduped. Severity is the highest any reviewer assigned.

| # | Severity | Finding | Raised by | Decision |
|---|---|---|---|---|
| 1 | CRITICAL | `from __future__ import annotations` reported UNUSED in every file that has one | live check | **Fixed** `9b4318c` |
| 2 | CRITICAL | `pytestmark` / `pytest_plugins` reported UNUSED; pytest reads them by introspection. Deleting a non-strict xfail mark yields a silent XPASS | Alice, Eve, Bob | **Fixed** `69fc859` |
| 3 | HIGH | `from x import *` reported as a binding literally named `*`; deleting takes every name the star supplied | Eve, Bob | **Fixed** `69fc859` |
| 4 | HIGH | `np = pytest.importorskip("numpy")` with `np` unread reported; deleting removes the skip guard and the suite passes wherever the dep is installed | Eve | **Fixed** `69fc859` |
| 5 | HIGH | `except ... as name` did not clear the SHADOWED tracker — `ast.ExceptHandler.name` is a plain `str`, never a Name node. PRD names this exclusion twice; it was implemented in neither place | Blake | **Fixed** `69fc859` |
| 6 | HIGH | The cycle-1 fix for #5 matched by ATTRIBUTE NAME, so `.name` also caught `FunctionDef`/`ClassDef`/`alias` — a nested `def`/`class`/import reusing a pending name silently swallowed a genuine shadow | Blake (c2), Eve (c2 KNOWN) | **Fixed** `fbc03f1` — scoped to node types |
| 7 | HIGH | Split-hygiene fix dispatch reused the task's own `ivan-<task-id>-files.txt`; `agents/ivan.md` makes a fixer stop on any unlisted file, so it dead-ended on the sibling module the style gate had just created | Eve | **Fixed** `0d1ec38` |
| 8 | MEDIUM | § Split-hygiene fix dispatch said "Two lines differ" after `0d1ec38` made it three; a literal reader keeps `FILE_PATHS` at the default and resurrects #7 | Alice (c2), Eve (c2) | **Fixed** `f3579f9`, now pinned by a test |
| 9 | MEDIUM | The test-path subset was named (`is_test_path`) but not constructible — no command, no argv shape | Bob, Eve | **Fixed** `f3579f9` — concrete filter, verified live |
| 10 | MEDIUM | Phase report demanded `split_hygiene: <value>` for every task, but haiku skips step 5.65 entirely | Eve, Bob | **Fixed** `0d1ec38` |
| 11 | MEDIUM | `test_both_records_enumerate_every_split_hygiene_value` could not fail for 3 of 4 values — they already appear via the `style_gate` row | Eve, Bob | **Fixed** `0d1ec38` — asserts the whole signature line |
| 12 | MEDIUM | Test name `…_keeps_the_task_allowlist` pinned the superseded design its own third assertion contradicts | Eve (c2) | **Fixed** `f3579f9` — renamed |
| 13 | MEDIUM | PRD-named exclusions with no regression test: `__all__` members, `with`, comprehension targets, `locals()`, fixture-as-argument, mixed non-Python exit-2 | Blake (c2), Bob | **Fixed** `fbc03f1` — 8 tests added |
| 14 | LOW | Test helpers `_unused`/`_shadowed` wrote a file neither rule reads | Eve | **Fixed** `69fc859` |
| 15 | HIGH→**REFUTED** | `handle = mocker.patch("a"); handle = mocker.patch("b")` reports the first; deleting the statement kills a live call | Bob | **Refuted** by Victor |

### Finding 15, refuted

Bob rated it HIGH; Eve had classified the same shape KNOWN. Contested HIGH, so
`autopilot:victor` verified it before I acted. Verdict REFUTED on four grounds,
each reproduced:

- The non-destructive repair — drop the name, keep `mocker.patch("a")` as a bare
  call — **exits 0**, so the ladder ends and nothing pushes a fixer toward
  deleting the RHS.
- `agents/ivan.md` rule 4 (rendered in full for this dispatch) forbids weakening
  tests and makes ambiguous scope a blocker.
- **0 SHADOWED across 1190 real test files** on this machine. The same sweep
  returned 29 UNUSED and flagged an injected control, so the empty result is
  measured, not a broken invocation.
- PRD § Risks books deliberate-rebinding false positives explicitly.

Victor's honest caveat, recorded: on a **test-only** task `test_only_gate` skips
Pat, so the step-7 suite is the sole backstop for exactly the PRD's headline
split scenario.

## Accepted as-is (recorded, not fixed)

- **`_is_import_guard` breadth** (Alice ⚪, Eve KNOWN, Victor LOW). It matches any
  `importorskip` identifier in the statement subtree, so `GUARDS = (pytest.importorskip,)`
  hides a dead binding. False negative only, on a shape absent from real test files.
- **`_is_import_guard` does not protect the SHADOWED rule**, only UNUSED
  (Victor). Needs two `importorskip` calls bound to one name in one function.
  Hardening it means deviating from the PRD's verbatim `RETRY_INSTRUCTION`; not
  worth it for a contrived case.
- **Scope-blind `Name`/`arg` clearing** (Eve KNOWN, probe-confirmed): a `lambda x:`
  in an RHS pops a tracked local `x`. Documented in `_clear`'s docstring.
  Conservative direction.
- **Exit 2 forfeits the fix dispatch for violations found in parseable files of
  the same batch** (Eve KNOWN). Mandated by the PRD's "any skip forces exit 2"
  and mirrors `check_style_limits.py`.
- **Side-effect imports and cross-module constants** (Bob). PRD § Risks accepts
  both; unlike `importorskip`, breakage is loud and the suite catches it.
- **The shadow rule does not descend into `if`/loop/`try` bodies** (Bob). This is
  deliberate: `if c: x = 1 else: x = 2` would otherwise be a false positive.
  Under-reporting is the safe direction for a deletion-only fixer.

## Live checks run

- Checker over all 33 test files in this repo: exit 0 after the fixes.
- Checker over 44 test/conftest files in `~/.claude/hooks/tests` and
  `buvis/agent-skills`: exit 0. Closes Eve's cycle-1 VERIFY item.
- Control run of the same sweep plus a planted `EXPECTED_ROWS = 12`: exit 1,
  reports exactly that line. Proves the sweep inspected rather than passed.
- Post-narrowing fixture: `except ... as caught` NOT reported, `handler = 1`
  before a nested `def handler()` REPORTED. Both in one run.
- The documented test-subset filter command, run for real: keeps
  `test_check_split_hygiene.py` and `conftest.py`, drops `check_split_hygiene.py`,
  `CHANGELOG.md` and `SKILL.md`.

## One true positive in pre-existing code

The widened sweep found `skills/review-work-completion/scripts/test_check_review_file.py:29`
— `mod = _load()`, bound and read nowhere in the file (`rg "\bmod\b"` returns
that one line). Real dead code the checker correctly caught. **Left alone**: it
is outside this PRD's diff and Surgical Changes says don't fix adjacent code.
Recorded here so it has a durable home.

It is also concrete evidence for the design point below.

## Known design point, as specified

`check_split_hygiene.py` takes no `--diff`, unlike `check_style_limits.py`. The
PRD's Exports pin `unused_bindings(tree, path)` and
`shadowed_assignments(tree, path)` with no diff parameter, and the rule is "is
this binding read anywhere in this file". Consequence: a task touching one line
of a large pre-existing test file inherits that file's pre-existing dead
bindings as violations — the `mod = _load()` hit above is exactly that shape.
The style gate deliberately scopes to the diff to avoid this. Implemented as the
PRD specifies; flagged for the operator.

## Deviations from the PRD

- The PRD says violations "route to the same single fix dispatch the style gate
  uses". Literally that is § Style-fix render, which hardcodes the widened
  directory allowlist — while the PRD also says "no allowlist widening is
  needed". Resolved toward § Retry render with a violation-derived file list.
- CHANGELOG entry landed in the first commit, per the drain plan's blocking rule,
  not in the last task.
- `split_hygiene` has no `skipped:tier` value; a haiku task skips step 5.65
  wholesale and the field is absent, documented the way `review` documents its
  haiku skip.
- SKILL.md had one line of headroom against its 500-line ceiling, so both
  step-5.65 additions extend existing paragraphs. Still 498 lines on disk.

## Process notes for the next session

1. **Bob needs an inlined prompt.** Referencing file paths fails even when the
   files are inside the workspace, because his persona forbids the commands that
   would read them. Assemble header + context + diff + PRD into one file.
2. **The plan's Blake block leaves `{RUBRIC}` and `{OUTPUT_FORMAT}` unbound.**
   Blake flagged this in both cycles and declined to emit `B{n}` verdict lines
   rather than invent numbering. He still produced the sharpest finding of the
   review both times, so this is a reporting gap, not a lens failure — but the
   plan's Blake block should bind those two placeholders.
3. A formatter in this environment rewrites scratchpad `.py` fixtures (it
   stripped `as caught` from a probe mid-session and briefly looked like a
   regression). Keep checker fixtures inside string literals, where the in-repo
   tests already put them.
