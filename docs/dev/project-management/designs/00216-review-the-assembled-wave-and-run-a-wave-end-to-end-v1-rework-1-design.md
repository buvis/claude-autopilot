# Design: rework cycle 1 — PRD 00216 CRITICAL

Source review: dev/local/reviews/00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1-review-1.md (head_sha fc5e559feb59baa9320f17127ed8ed6b8870cfa0)

## Architecture fit

Prior fix: none - there was no prior rework fix.

The one 🔴 row this cycle closes, verbatim from the review's `## Consolidated Findings`:

> [2/4] 🔴 `autopilot wave run` crashes on every real invocation: `run_p` registers no `--state`, but `__main__._run_wave` reads `args.state` first. Reproduced: `python3 skills/run-autopilot/cli/__main__.py wave run` exits 1 with `AttributeError: 'Namespace' object has no attribute 'state'` before `wave_run.run` is reached; `wave run --state …` is rejected as an unrecognized argument. The PRD's headline verb, the documented `autoclaude wave` alias and the CHANGELOG entry advertising it are all unusable. `test_wave_cli_registers_review_land_run_as_wave_subverbs` only parses argv and every `test_run_*` calls `wave_run.run` directly, so no test goes through `main()` | skills/run-autopilot/cli/wave_cli.py:29 | 5 | ALICE, BLAKE

This was introduced by the cycle's own work (task 5 added the three verbs), not merely exposed by it: `wave run` did not exist before `3bb4d18`.

The defect sits at the seam between two files that PRD 00214 already established and this PRD extended:

- `cli/wave_cli.py` `add(subparsers)` builds the `wave` verb group. Every pre-existing verb registers `--state` on its own sub-parser (`wave_cli.py:21-28`): `plan` explicitly, `launch`/`status`/`abort` through a loop, `assemble`/`review`/`land` one per line. `run` (`wave_cli.py:29-32`) registers `--max-lanes`, `--review-slots` and `--yes`, and no `--state`.
- `cli/__main__.py` `_run_wave(args)` (`:1150-1164`) opens with `state_path = _resolve_state_path(args.state)`, unconditionally, for every verb in the group. It is the single place the repo root and `wave.json` path are derived, exactly as the module docstring of `wave_cli.py` says ("resolving them from `--state` stays in `cli/__main__.py`, like every other subcommand").

So the group's dispatcher has a contract — *every* `wave` sub-verb carries a `--state` attribute — that the parser stopped honouring for one verb. Nothing in the layering is wrong; one registration line is missing.

`_resolve_state_path` (`__main__.py:218-221`) already handles the no-flag case: `raw is None` walks up from cwd to the autopilot dir. That is why `--state` is optional on every other verb and why adding it to `run` is sufficient — a bare `autopilot wave run` then resolves by walking up, which is what the PRD's `autoclaude wave` alias (`caffeinate -is python3 "$_skill/cli/__main__.py" wave run "$@"`, passing no `--state`) needs.

**Root cause of the escape, which the fix must also close.** The untested edge is `parse -> dispatch` **for the `wave` verb group** — not for the CLI as a whole. (An earlier draft of this paragraph claimed no test drives `main()` at all, from an `rg` that only covered three in-process spellings. That was false and is corrected here: the repo drives `main()` by **subprocess** — `test_cli_default_paths.py:35,40` defines `CLI_MAIN` and `_run()` as `subprocess.run([sys.executable, str(CLI_MAIN), *args], cwd=…)`, used by seven test classes including walk-up-from-nested-cwd and explicit-`--state` cases, and `test_cli.py:724` `test_every_subcommand_succeeds_as_a_subprocess_from_any_cwd` drives six subcommands through the real `main()` from several cwds.)

What no test does is reach a **wave** verb through the real parser and dispatch table. `test_wave_cli_registers_review_land_run_as_wave_subverbs` builds the parser through `add()` and asserts `args.verb` is set, which passes while `args.state` is absent; every `test_run_*` calls `wave_run.run(...)` directly. That is the hole `run` fell through.

**Why not just extend the existing subprocess harness.** A subprocess cannot intercept the verb below the dispatcher, so a parameterised `wave` sweep run that way would really execute `plan`, `launch`, `abort` and `land` — creating worktrees and mutating git. The in-process `main(argv)` call with a monkeypatched `wave_cli.run` is the seam that lets every verb be swept safely. `test_cli.py:724` stays the right harness for subcommands whose execution is harmless; this test is the wave-group counterpart, not a duplicate of it.

## Module placement

Edits to existing files only. No new module.

- `skills/run-autopilot/cli/wave_cli.py` — one added line in `add()`: register `--state` on `run_p`.
- `skills/run-autopilot/cli/test_wave_run.py` — **new file, unconditionally**, holding the regression test. Not `test_wave_review.py`: that file is already 1141 lines against the 800 ceiling, and a sibling task this same cycle is assigned to split it into exactly this filename. Ordering-dependent placement ("put it here unless the other task ran first") invites a merge conflict or a silently lost test, so this task creates the file and the sibling moves the `test_run_*` cases into it afterwards.
- `dev/bin/release-checks` — add `test_wave_run.py` to the `[checks] waves` pytest block (`:107-119`).
- `skills/run-autopilot/cli/test_wave_docs.py` — add `test_wave_run.py` to `_WAVE_TEST_FILES` (`:41`). **Both registrations are mandatory, not housekeeping:** `test_wave_docs.py:103` asserts set *equality* between that list and the release-checks block, so adding the file to one side alone turns that gate red.

## Interfaces & contracts

Closes: `[2/4] 🔴 autopilot wave run crashes on every real invocation: run_p registers no --state, but __main__._run_wave reads args.state first.`

`skills/run-autopilot/cli/wave_cli.py`, inside `add(subparsers)`, on the existing `run_p` sub-parser — one line, placed with the other `run_p.add_argument` calls:

```python
    run_p = verbs.add_parser("run")
    run_p.add_argument("--state")
    run_p.add_argument("--max-lanes", type=int, default=3)
    run_p.add_argument("--review-slots", type=int, default=3)
    run_p.add_argument("--yes", action="store_true")
```

`--state` takes argparse's defaults here — no `type`, no `default`, no `required` — exactly as the seven sibling registrations do (`wave_cli.py:22`, `:25`, `:26`, `:27`, `:28`). The resulting `args.state` is `None` when the flag is absent, which `_resolve_state_path` (`__main__.py:218-221`) resolves by walking up from cwd. Do **not** give it a default path, a `required=True`, or a distinct dest: any of those diverges `run` from the group contract `_run_wave` relies on and from the alias's no-flag invocation.

No change to `_run_wave`, `_resolve_state_path`, `wave_cli.run` or `wave_run.run`. For the two forms this fix covers — the flag absent, and an absolute canonical `--state` — their behavior is correct as written; the parser was the only thing out of contract.

Narrower than it first reads, deliberately: a **relative** `--state` of canonical shape passes the `parts[-5:]` guard (`__main__.py:1156`) and then yields `repo = Path('.')` from `parents[4]`, because `_resolve_state_path` returns `Path(raw)` unresolved. Measured. That is pre-existing and shared by all seven other wave verbs, so it is **not** closed here and must not be claimed as correct — it belongs in its own row, not in a CRITICAL fix.

The regression test's contract — it must exercise the real `parse -> dispatch` edge, which is the surface that had no coverage:

```python
def test_every_wave_verb_parses_and_dispatches_with_no_state_flag(...):
    """`autopilot wave <verb>` reaches wave_cli.run with a resolvable state
    path for every verb, instead of dying in _run_wave on a missing
    args.state. Drives cli.__main__.main(argv) - the real parser and the
    real dispatch table - not wave_cli.add() alone."""
```

Shape requirements, all load-bearing:

- Call `__main__.main(["wave", "<verb>", ...])` for **every** verb the group registers — `plan`, `launch`, `status`, `abort`, `assemble`, `review`, `land`, `run`. Parameterise over the verb list rather than testing `run` alone; a test that pins only today's bug lets the next one through the same hole. **Derive the verb list from the built parser** (read the `wave` sub-parser's own registered choices) rather than hand-listing the eight, so a verb added later is covered automatically. If it must be hand-listed, add an assertion that the list equals the parser's registered wave verbs — otherwise a new verb can be omitted from the list while the test stays green, which is this same bug's next instance.
- Monkeypatch exactly one seam: `monkeypatch.setattr(wave_cli, "run", recorder)`, a recorder returning 0, so the test asserts the dispatch was *reached* with the resolved paths. `__main__` holds `wave_cli` as a module attribute and calls it by attribute lookup (`__main__.py:1165`), so the patch takes effect. **Patch nothing below that point** — patching the verb implementations instead (`wave.plan`, `wave_launch.launch`/`abort`, `wave_assemble.assemble`, `wave_review.review`/`land`) would let `_run_wave` run for real. Intercepting there means **no verb implementation** runs: no git, no spawn, no wave mutation from any of the eight. (The fixture setup itself still runs git — `_repo` does `init`/`config`/`add`/`commit`, `test_wave_launch.py:64` — which is ordinary for this suite. The claim is about the dispatch, not the setup.)
- Run with cwd inside a `tmp_path` directory holding `docs/dev/project-management/autopilot/`, so the walk-up branch of `_resolve_state_path` is the one under test. That directory is all this needs: prefer creating it directly over the full `_repo` helper, which runs `git init`/config/add/commit per case (~40 subprocesses across an eight-verb sweep) for a parser test that touches no git. Follow the sibling modules' import-a-helper convention rather than adding a new fixture module.
- Assert **no exception escapes** and the recorder was called. An `AttributeError` from `_run_wave` must fail the test, which is the exact failure the current code produces.
- Also assert the explicit-flag form works: `main(["wave", "run", "--state", str(state_path)])` reaches the same recorder. Today argparse rejects it as an unrecognized argument, so this half fails against the unfixed code too.

## Data flow

`argv` -> `_build_parser()` (`__main__.py:1238-1243`, which calls `wave_cli.add(subparsers)`) -> `main()` looks up `_SUBCOMMANDS["wave"]` -> `_run_wave(args)` -> `_resolve_state_path(args.state)` -> canonical-path check (`__main__.py:1156`) -> `repo = state_path.parents[4]`, `wave_path = state_path.parent / "wave.json"` -> `wave_cli.run(args, repo, wave_path)` -> `wave_run.run(repo, ...)`.

The fix restores the second-to-last hop for `run`. Nothing downstream of `_resolve_state_path` changes, and nothing upstream of `add()` changes.

## Reuse inventory

- **`verbs.add_parser("<verb>").add_argument("--state")`** — `skills/run-autopilot/cli/wave_cli.py:22,25,26,27,28`. The exact idiom for this registration, used by all seven sibling verbs. Reuse it verbatim; do not introduce a shared helper for one added line.
- **`_resolve_state_path(raw)`** — `skills/run-autopilot/cli/__main__.py:218-221`. Already implements "flag absent -> walk up from cwd". No new resolution logic is needed, and none should be added.
- **`__main__.main(argv)`** — `skills/run-autopilot/cli/__main__.py:1246-1249`. Takes an explicit `argv` list, so a test drives the real parser and the real dispatch table in-process with no subprocess.
- **`_repo` / `_planned` / `_FakeSpawn`** (`test_wave_launch.py`) and **`_pm`** (`test_wave_review.py:193`) — the established fixtures for a tmp_path repo with the project-management tree. The test strategy outline below reuses these; `test_wave_review.py` already imports across siblings this way.
- **`_run()` subprocess CLI harness** — `skills/run-autopilot/cli/test_cli_default_paths.py:35,40` (`CLI_MAIN`, `subprocess.run([sys.executable, str(CLI_MAIN), *args], cwd=…)`), and `test_cli.py:724` `test_every_subcommand_succeeds_as_a_subprocess_from_any_cwd`. These already drive the real `main()`. **Deliberately not reused here**, for the reason in `## Architecture fit`: a subprocess executes the verb for real, so sweeping all eight wave verbs that way would create worktrees and mutate git. Read them for the cwd/`--state` fixture patterns, then use the in-process seam instead. (An earlier draft of this bullet claimed no main()-level test existed at all; that was a too-narrow grep and is corrected.)
- `~/.claude/rules-library/rationalizations.md` was not consulted for synonym sets: the sweep here is for one known symbol pair (`--state` registration, `args.state` consumption) with both sides already located by file:line, not an open-ended capability search.

## Alternatives considered

1. **Chosen: add `--state` to `run_p`, plus a parameterised `main()`-level dispatch test over every wave verb.** Smallest change that closes the finding (one line) paired with the smallest test that would have caught it and will catch the next one. The test costs more than the fix, deliberately: the review found the bug in under a minute by running the command, while the existing suite was green, so the missing coverage is the real defect.
2. **Smallest possible diff: the one line, no test.** Rejected. `rules/testing.md` requires a regression test with every bug fix, and the whole reason this shipped is that no test drives `main()`. Fixing the line without closing the hole leaves the next verb registration free to repeat it.
3. **Make `_run_wave` defensive — `getattr(args, "state", None)`.** Rejected: it papers over the contract rather than restoring it. Every wave verb is supposed to accept `--state`; a verb that silently loses the flag would then resolve by walk-up while the operator believes their `--state` was honoured, and `wave run --state <path>` would still be an argparse error. It also spreads the group's invariant across two files instead of keeping it in the parser.
4. **Register `--state` once on the `wave` parser itself instead of per verb.** Genuinely tempting — it would make the whole class impossible — but rejected for this cycle: argparse accepts a parent-level option only *before* the sub-verb, which breaks the documented `wave run --state X` form every caller and test already uses, including `references/waves.md`. **Verified, not assumed** — a probe building exactly that parser shape gives:

   ```
   ['wave', '--state', 'X', 'run'] -> {'command': 'wave', 'state': 'X', 'verb': 'run'}
   ['wave', 'run', '--state', 'X'] -> SystemExit    # error: unrecognized arguments: --state X
   ```

   The compatibility that breaks is the **post-verb flag form the existing tests already use** — `test_wave_review.py:1129` parses `["wave", "review", "--state", …]` and `["wave", "land", …]` that way — not a documented example: `references/waves.md`'s § wave run does not show `--state` at all. So read the post-verb form as the group's real contract, evidenced by its call sites, rather than by prose.

   (That probe used a stock `argparse.ArgumentParser`, so it exits 2. Inside this CLI the same parse error exits **1**: `_ArgumentParser.error` (`__main__.py:195-202`) overrides argparse's native 2 because "exit 2 is reserved for state errors", and subparsers inherit the override. The ordering conclusion is unchanged; only the code differs.)

   Worth revisiting as its own change together with the docs and every call site, not inside a CRITICAL fix.

## Risks & edge cases

- **The parameterised test must not execute real verbs.** `plan`, `launch`, `abort` and `land` mutate git and the filesystem. The recorder must intercept at `wave_cli.run` (or the dispatch entry), not below it, or the test itself starts wave lanes. This is the one way this test can do damage; it is also why the assertion is "dispatch reached", not "verb succeeded".
- **Canonical-path guard interaction.** `_run_wave` refuses a `--state` whose last five parts are not `docs/dev/project-management/autopilot/state.json` (`__main__.py:1156-1162`). The explicit-flag half of the test must pass a canonical path, or it will assert exit 1 for the wrong reason. The walk-up half needs the tmp repo's `docs/dev/project-management/autopilot/` to exist.
- **Likely next changes this must not box in.** (1) The sibling `[D1]` task adds a TTY confirmation prompt to `wave_run.run`; the test here stops at `wave_cli.run`, so it is unaffected by that and must stay that way — do not extend it to assert on `wave_run.run`'s internals. (2) The sibling style-limit task moves the `test_run_*` cases into `test_wave_run.py` — the file this task creates and registers, so that task inherits an existing, already-gated file rather than racing to create it. (3) A future `wave` verb: the parameterised verb list is what makes it covered automatically, provided the list is derived from, or kept in step with, the registered verbs.
- **Three tasks touch `wave_cli.py` this cycle**: this one, the error-contract task (wrapping the `review`/`land`/`run` dispatches, `:73`) and the style-limit task (getting `run()` under 50 lines, `:35`). The other two both edit `run()`; this one edits `add()` only, so they compose — but they must not be dispatched in parallel against the same file.
- **What this fix does not do:** it does not make `wave run` work end to end. Six HIGH findings (the TTY gate, the missing summary lines, `interrupted`, `land`'s resumability and cleanup, the tracked-store premise) remain open in their own tasks. Closing the CRITICAL means the verb is reachable, not that the wave lifecycle is correct.

## Test strategy outline

One new test, parameterised over the eight registered wave verbs, in whichever module holds the `test_run_*` cases:

- **Fixture**: `monkeypatch.chdir(repo)` so the walk-up resolution has a tree to find. A full `_repo` (`test_wave_launch.py:64-78`) is heavier than this needs — it runs `git init`, two configs, an add and a commit per case, roughly 40 subprocesses across an eight-verb sweep of what is only a parser test. Creating `docs/dev/project-management/autopilot/` under `tmp_path` is sufficient; note `_repo` already creates it at `:70`, and `_pm` (`test_wave_review.py:193`) only computes a path, so pairing the two is redundant. Use `_repo` only if a case genuinely needs a git repo.
- **Seam**: `monkeypatch.setattr(wave_cli, "run", recorder)` where `recorder(args, repo, wave_path)` appends `(args.verb, repo, wave_path)` and returns 0. Nothing below the dispatcher runs.
- **Case A (no flag)**: for each verb, `assert __main__.main(["wave", verb]) == 0` and the recorder saw that verb with `wave_path == repo/"docs/dev/project-management/autopilot/wave.json"`. Fails today for `run` with `AttributeError`.
- **Case B (explicit flag)**: `__main__.main(["wave", "run", "--state", str(canonical_state_path)])` reaches the recorder. Fails today with an unrecognized-argument `SystemExit(1)` — **1, not argparse's native 2**, because `_ArgumentParser.error` (`__main__.py:195-202`) overrides it and subparsers inherit that override. Verified by running the real `main()` against the unfixed code.
- **Fail-first is mandatory here** (`rules/testing.md`): run both cases against the unfixed `wave_cli.py` and watch them fail with those two distinct errors before adding the registration line.
- **Regression guard**: `test_wave_cli_registers_review_land_run_as_wave_subverbs` stays as-is and green — it pins verb registration, this pins dispatch.
- **Suite**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_wave_review.py` (or the split file), then `bash dev/bin/release-checks`.

## Review log

- **Process deviation, recorded rather than hidden**: dispatches 1 (claude) and 2 (codex) were launched concurrently to save wall-clock, where this skill says "one reviewer dispatch per loop iteration; never two in flight at once". The cost is real and is stated here: codex reviewed the draft *before* dispatch 1's blocker was fixed. It is mitigated by the codex engagement re-run, which read the doc after the first round of corrections, and by dispatch 1's own blocker being about a claim codex did not touch. No dispatch-3 verification pass ran, because dispatch 2 returned zero cardinal sins and zero blockers, which is this skill's condition for skipping it.
- blocker (dispatch 1, claude): "The doc's root cause and reuse inventory rest on a too-narrow grep: main()-level CLI tests already exist". The draft claimed no test drives `__main__.main()`, from an `rg` covering only three in-process spellings; the repo drives it by subprocess (`test_cli_default_paths.py:35,40`, `test_cli.py:724`). **Verified independently before fixing** — both citations check out. Fixed in `## Architecture fit` (the claim is now the narrower, true one: no test reaches a *wave* verb through the real parser and dispatch) and in `## Reuse inventory` (the harness is now listed as existing and deliberately not reused, with the reason).
- non-blocker (dispatch 1, claude): Case B predicted `SystemExit(2)`; the CLI's `_ArgumentParser.error` exits 1. Same finding as codex dispatch 2's first. **Fixed** in `## Test strategy outline` and `## Alternatives considered` — a wrong expected code in a verbatim-copied contract would send the implementor to write a failing fail-first step.
- non-blocker (dispatch 1, claude): alternative 4 was rejected citing `references/waves.md` and the alias as users of `wave run --state X`; neither is (waves.md contains no `--state` at all, and the form is an argparse error today). The mechanism is right, the evidence was not. **Fixed** — the rejection now rests on the existing tests' post-verb flag form (`test_wave_review.py:1129,1132`).
- non-blocker (dispatch 1, claude; also codex dispatch 2's second): a hardcoded eight-verb list does not deliver the "catches the next verb" guarantee the contract claimed. **Fixed** — the contract now requires deriving the verb list from the built parser, or asserting the list equals the parser's registered verbs.
- non-blocker (dispatch 1, claude): primary placement grew `test_wave_review.py`, the very file a same-cycle sibling task must split, with ordering-dependent wording. **Fixed** — `test_wave_run.py` is now created unconditionally by this task, with both mandatory registrations (`release-checks` `[checks] waves`, `test_wave_docs.py:41` `_WAVE_TEST_FILES`) named, since `test_wave_docs.py:103` asserts set equality between them.
- non-blocker (dispatch 1, claude): "`_run_wave` … behavior correct as written" is refuted by a relative `--state`, which yields `repo = Path('.')`. **Fixed by narrowing** the claim to the absent-flag and absolute-path forms; the relative-path resolution is recorded as pre-existing, shared by all seven other wave verbs, and explicitly not closed here.
- question (dispatch 1, claude): the seam instruction's parenthetical ("or `_SUBCOMMANDS["wave"]`'s run function's callees") could be read as patching the verb implementations, which `## Risks & edge cases` forbids because it would start real wave lanes. **Fixed** — the parenthetical is gone; one seam is named, with the attribute-lookup reason it works.
- non-blocker (codex dispatch 2 re-run): the test setup does run git via `_repo`, so "performs no git" was imprecise. **Fixed** by narrowing the claim to the dispatch, and the fixture guidance now prefers the lighter setup.
- non-blocker (codex dispatch 2 re-run): the accepted future-verb coverage limitation was not recorded in this log. **Recorded here**, and superseded by the derive-from-parser fix above.
- dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 5, question 1
- dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 2, question 0
- dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 3, question 0
- Dispatch 2 returned 2 findings on its first pass, under the minimum-engagement threshold of 3, so that reviewer was re-dispatched once with a sharpened prompt naming all eight sections. The re-run returned 3 non-blockers plus a per-section `checked, correct` list with a file:line or doc-section anchor on every entry, so dispatch 2 is **not** marked weak. Both its passes are logged above; the engagement re-run does not consume the 3-dispatch ceiling.
- No open cardinal sins or blockers remain: the single blocker was fixed and independently verified, and both codex passes found none.

result: ok
