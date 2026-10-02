# agoge strategy profile: claude-autopilot

Repo root: `/Users/bob/git/src/github.com/buvis/claude-autopilot` (written as `$R` below; specialists must expand it, never `cd` into it).
Python: uv-managed cpython 3.13.13. No `pyproject.toml`, no `package.json`: every runner is `uv run --no-project --with <deps>`.

## 1. Surfaces

### LIVE LOOP WARNING (measured 2026-10-02T22:56Z)
- PID 88048 `caffeinate -is python3 ~/.claude/plugins/cache/buvis-plugins/autopilot/0.6.0/skills/run-autopilot/cli/__main__.py loop`, cwd = `$R`. It runs the installed 0.6.0 cache, not this checkout, so the PRD 00236 verbs below (`ensure-store` etc.) are NOT what the loop executes.
- At measure time `$R/docs/dev/project-management/autopilot/` held `state.json.bak` + `state.json.lock` but no `state.json`, `.session-left` dated 00:49 local, `last-session.log` written 00:55 local. `prds/wip/` empty. A session may start at any moment.
- Rules for every lane: never run `autopilot loop`, `review-once`, `enter`, `init`, `stall`, `park`, `phase-done`, `record-store`, `ensure-store`, `wave launch|run|assemble|land|abort`, or `custody resolve` against `$R`. `record-store` makes a real git commit and `ensure-store` writes `.gitignore`: fixture only. Never run a hook or CLI with process cwd inside `$R` (the cap hook and `--state` resolution walk up from cwd and write markers). Use a `/tmp` fixture tree and pass `--state` explicitly. Pass `-p no:cacheprovider` to pytest so `.pytest_cache` is not rewritten. Re-check `git -C $R status --short` after any run (was clean after every recon run).

### Test suites (pytest, ran it)
- Collect all (cwd `/tmp`): `uv run --no-project --with pytest python -m pytest -p no:cacheprovider --collect-only -q $R/skills $R/hooks` -> **4401 collected, 3 collection errors** (was 4273 at c8bbe2b). The 3 are `skills/run-autopilot/scripts/tracon/test_{panels,screens,stream}.py`: `ModuleNotFoundError: No module named 'rich'`. Not a code defect: tracon needs extras.
- tracon suite: `uv run --no-project --with pytest --with rich --with textual python -m pytest -p no:cacheprovider -q $R/skills/run-autopilot/scripts/tracon` (collected 361 clean at c8bbe2b; not re-run).
- Full suite incl. tracon: `uv run --no-project --with pytest --with pytest-xdist --with rich --with textual python -m pytest -p no:cacheprovider -q -n auto --maxprocesses 4 $R/skills $R/hooks` (cap workers at 4, PRD 00233). Not run in full during recon.
- Ran green this recon (cwd `/tmp`): `... -q $R/hooks` -> 86 passed, 195 subtests passed, 2.7s. The 11 store-tree modules (the 10 in release-checks' `store tree` block plus `cli/test_store_tree_legibility.py`) with `-n 4` -> 165 passed, 4 subtests passed. `test_store_tree_legibility.py` alone -> 10 passed.
- Ran green at c8bbe2b (not re-run): `$R/skills/fast-track/scripts` -> 202 passed.
- Release gate: `bash $R/dev/bin/release-checks` (expects cwd = repo root; relative paths). Now ~24 pytest blocks incl. a new `[checks] store tree` block (10 modules: `cli/test_store_tree_{foreign_dirty,record_store,cli,custody,gitignore}.py`, `cli/test_store_gitignore.py`, `cli/test_store_boundary.py`, `cli/test_store_lane.py`, `cli/test_loop_record_store.py`, `scripts/test_store_tree_prose.py`) and an `enter` block, plus the bash tests. Run it only from a `git worktree` copy: `bash -c 'cd <worktree-copy> && bash dev/bin/release-checks'`. Not run whole during recon.
- **Gate gap (noted, not fixed):** `skills/run-autopilot/cli/test_store_tree_legibility.py` (task 12, PRD 00236; 10 tests) appears nowhere in `dev/bin/release-checks` (`rg legibility` -> nothing; no block passes the `cli/` directory wholesale, all 59 cli references are explicit files). HEAD `1daea55` fixed the split-module paths but left this one ungated.
- Bash tests (stubbed CLIs, no network): `bash $R/skills/use-sonnet/scripts/test_sonnet_run.sh` -> 27 passed at c8bbe2b. Siblings: `$R/skills/use-codex/scripts/test_codex_run.sh`, `test_codex_run_resume.sh`, `$R/skills/use-gemini/scripts/test_gemini_run.sh`, `$R/skills/review-work-completion/scripts/test_gather_context_paths.sh`.
- Noted, not alarming: pytest-of-bob temp cleanup warnings (`Errno 66`) on every run; harmless. Old note about a stale `__pycache__` path in the `test_stream.py` traceback still applies.

### CLI entry points (ran `--help`, cwd `/tmp`)
- `python3 $R/skills/run-autopilot/cli/__main__.py --help` -> subcommands `init enter stall park reset-prd defer restore check-plan select frontmatter lane-check phase-done resume-target gate render status loop review-once custody mint-stubs dirty record-store ensure-store wave` (`ensure-store` new since c8bbe2b). Cold start 0.05s.
- New/changed store verbs: `ensure-store [--state]`, `dirty [--state]`, `record-store [--state] --site SITE [--prd PRD]`.
- Fixture journey proven this recon in `/tmp/olivia-fx2` (git repo, state `/tmp/olivia-fx2/docs/dev/project-management/autopilot/state.json`): `init --state S --prd 00001-x.md` exit 0 -> `ensure-store --state S` prints the `.gitignore` path, exit 0, writes a 23-line `STORE_GITIGNORE` (state.json, .bak, locks, markers, lanes/, wave.json, logs, session-brief, contract-card, last-verification) -> `dirty --state S` with only store dirt: no output, exit 0 -> `record-store --state S --site test` exit 0, prints sha, commits `chore(autopilot): record test state` touching only the `.gitignore` (state.json is ignored by design) using the operator's global git identity -> add `foreign.txt` -> `dirty` prints `foreign.txt`, exit 1.
- Older fixture journey (c8bbe2b, `/tmp/olivia-fx`): `init` -> `status` -> `resume-target` -> `select --prds ...` (`{"prd": null, "source": "drained"}`).
- `wave --help` -> `plan launch status abort assemble review land run` (c8bbe2b).
- `python3 $R/skills/fast-track/scripts/card.py --help` -> `card.py card`; fixtures under `skills/fast-track/scripts/fixtures/`.
- tracon (Textual TUI, not a browser): `uv run --no-project --with rich --with textual python $R/skills/run-autopilot/scripts/tracon.py --help`.
- Other scripts with CLIs (not individually probed): `skills/run-autopilot/scripts/{statectl,fablectl,tune_routing,render_stream,codex_review_run,detect_usage_limit}.py`, `skills/work/scripts/*.py`, `skills/review-work-completion/scripts/*.py`, `skills/plan-tasks/scripts/classify_tier.py`, `skills/use-codex/scripts/codex_hook_doctor.py`.

### Hooks (stdin JSON, ran them)
- Registered in `$R/hooks/hooks.json`: PreToolUse `enforce_prd_location.py` (Edit/Write/MultiEdit/Bash), `guard_push_on_critical.py` (Bash, 10s), `guard_skill_after_leave.py` (Skill); PostToolUse `autopilot_context_cap_hook.py`, `validate_state_json_hook.py`, `note_session_leave.py`; Stop `review_coverage_hook.py`, `guard_stop_on_live_lanes.py`. All `python3`, 5s unless noted. Block = exit 2 + stderr.
- Probe shape: `bash -c 'cd /tmp && python3 $R/hooks/enforce_prd_location.py <<< "<json>"; echo exit=$?'`. This recon: a Write to `/tmp/olivia-fx2/docs/dev/project-management/intake/note.md` -> exit 0 (the new intake-tree allowance, commit `9815f62`). At c8bbe2b: `mv 00001-x.md backlog/` Bash payload -> exit 2; benign/malformed input to the push guard -> exit 0.
- `autopilot_context_cap_hook.py` writes markers into the autopilot dir found by walking up from **process cwd**: only invoke it with cwd inside a `/tmp` fixture.

### Dev server / browser
- No server, no HTML/JS/CSS/package.json outside `docs/` (c8bbe2b `rg --files`; the 40 new commits touch only `skills/run-autopilot`, `skills/fast-track` docs, `hooks`, `dev/bin/release-checks`, CHANGELOG).
- Playwright browsers cached in `~/Library/Caches/ms-playwright`, nothing to point them at.

### Database
- None. State is JSON/JSONL under `docs/dev/project-management/autopilot/`. New: `docs/dev/project-management/.gitignore` (STORE_GITIGNORE) decides which store files are tracked; `$R` already has one.

### External services
- `cli/loop.py` probes `https://api.anthropic.com` (urllib, 5s) before spawning sessions.
- Spawned CLIs present: `claude`, `codex`, `gemini`, `copilot`. Live calls cost money and quota.
- `dev/bin/release` shells into sibling `$R/../claude-plugins/scripts/release-plugin`. Never run it.
- `git` is the main integration partner: custody, wave worktrees, store_tree, and now `record-store` commits via `custody.store_git`.

### Release metadata (read)
- Tags `v0.1.0`..`v0.6.0`; `.claude-plugin/plugin.json` and `marketplace.json` say `0.6.0`; root `$R/plugin.json` still says `0.1.0` (drift, unchanged).
- `git log c8bbe2b..HEAD`: 40 commits, all PRD 00236 plus the hooks intake fix. `[Unreleased]` now covers: hooks intake fix (Fixed); store no longer trips clean-tree gates, store boundary from the work-tree + `status.showUntrackedFiles`, store commits out of lane routing/wave lanes (Changed). **Not mentioned anywhere in CHANGELOG or README**: the `autopilot ensure-store` verb and the shipped store `.gitignore` (`feat` commits `dcd3293`, `13eb749`, `842c31f`), and the `dirty` / `record-store` verbs by name (`rg "ensure-store|record-store|autopilot dirty|STORE_GITIGNORE"` over CHANGELOG.md and README.md -> nothing). The `fix` commits for review-once store recording (`58d8b28`) and store-failure legibility (`73cfb34`) also have no explicit line.

## 2. Per-specialist strategy

| Specialist | Verdict | Tactics / reason |
|---|---|---|
| walter (journeys) | **armed** | Drive the `autopilot` CLI end to end in a fresh `/tmp` fixture repo (`git init`, `docs/dev/project-management/{autopilot,prds/{backlog,wip,hold,done}}`), cwd in the fixture, `--state`/`--prds` always explicit. Journey 1 (new, PRD 00236 store lifecycle): `init` -> `ensure-store` (twice: idempotent? read-only store dir must still exit 0 per `1a2dba6`) -> `dirty` with store-only dirt (expect exit 0, no output) vs foreign dirt (expect exit 1 + paths) vs a store nested below the work-tree root -> `record-store --site <x> [--prd]` (commit made, only store paths, ignored files excluded) -> `record-store` with nothing to record. Journey 2: `init` -> `frontmatter` -> `check-plan` -> `phase-done` -> `status` -> `render ... --stdout` -> `stall`/`park` -> `restore`. Check every exit code against the docstring table in `cli/__main__.py`. Journey 3: fast-track `card.py` over `fixtures/*.md`. Journey 4: `wave plan`/`status` only (never `launch`/`run`). Never against `$R`. |
| heidi (integration/db) | **armed** (git + file-store integration; no DB) | No database. Integration surfaces: git and the JSON/JSONL store. New focus: store boundary derivation (`store_tree`) against a bare-repo-backed fixture (`git --git-dir=<bare> --work-tree=<root>` with the store several levels below the root, like `$HOME/.claude`), `status.showUntrackedFiles=no|normal|all` in the fixture's config, store commits interleaved with code commits then `lane-check` (store commits must not escalate the lane), `ensure-store` on a pre-existing hand-edited `.gitignore`, `record-store` when the store is ignored or git fails (legible error, exit code). Keep the older tactics: concurrent `state.transaction` writers on one fixture `state.json`, corrupt `state.json`/`.bak`, future `schema_version` (exit 6), `custody list/resolve` on fixture repos. Read first: `cli/test_store_tree_*.py`, `test_store_boundary.py`, `test_store_lane.py`, `test_custody*.py`. |
| judy (UX/browser) | **unarmed** | No browser surface: no HTML/JS/CSS, no `package.json`, no server (c8bbe2b `rg --files`; none of the 40 new commits add one). Playwright browsers are cached but have nothing to load. The Textual TUI `tracon.py` is not a browser and is covered headless by `tracon/test_screens.py`. |
| wendy (release truth) | **armed** | Read-only: (1) `git -C $R log --oneline v0.6.0..HEAD` vs `CHANGELOG.md` `[Unreleased]`: `ensure-store` verb + shipped store `.gitignore` (three `feat` commits) have no entry; `dirty`/`record-store` never named; review-once store recording and store-failure legibility fixes not listed. (2) Gate truth: `[Unreleased]`/commit `5ab1a1f` say the store-tree suites are gated, but `cli/test_store_tree_legibility.py` is absent from `dev/bin/release-checks`. (3) Version drift `$R/plugin.json` 0.1.0 vs 0.6.0 manifests. (4) README counts ("Eleven skills", "Fourteen agents", "Two hooks") vs `skills/*/SKILL.md`, `agents/*.md`, hooks.json. (5) `--help` subcommand list vs `skills/run-autopilot/SKILL.md` and `references/*.md` (does any doc tell sessions to run `ensure-store`, `dirty`, `record-store` with the exact flags the parser accepts, e.g. `--site` is required). Never run `dev/bin/release`. |
| peggy (performance) | **armed** | (1) Hook latency vs hooks.json budgets (5s; 10s push guard): repeat-run every hook with large payloads, cwd in a `/tmp` fixture (5 push-guard runs took 0.21s at c8bbe2b). (2) CLI cold start: `--help` 0.05s this recon; time `dirty` and `record-store` on a fixture with 10k untracked files and a deep store (they shell to `git status`; `showUntrackedFiles=all` vs `normal` matters). (3) Release gate wall time in a worktree copy, incl. the new serial `store tree` block (165 tests ran in 0.53s with `-n 4`; serial cost unmeasured). (4) `render metrics --metrics <file>` over a 100k-row `loop-metrics.jsonl` (the live one is 89 KB; copy, never read in place while the loop writes). |
| trudy (runtime security) | **armed** (surface) | Hostile-input surfaces: hook stdin JSON (8 hooks), CLI args, parsed files (`state.json`, `wave.json`, deferred ledger, custody journal, PRD frontmatter, spec cards, transcripts), and now git-derived paths in the store verbs. Tactics, all in `/tmp` fixtures: (a) `guard_push_on_critical.py` bypass grammar (`git -C`, `--git-dir`, `env git push`, `$(...)`, `cd x && git push`, `git -c alias.p=push p`) with a pending cap_critical marker; expect exit 2. (b) `enforce_prd_location.py` evasion now that `intake/` is accepted: can a PRD land via `intake/../prds/...`, a symlinked `intake`, case variants, or `MultiEdit`/Bash `mv` into `intake/` then out. (c) `record-store --site` / `--prd` with newlines, `--`-prefixed values, shell metacharacters, very long strings (they reach a commit message and git argv); a store path that is a symlink out of the repo (does `record-store` commit files outside the store?). (d) Malformed/huge/non-UTF-8 stdin to every hook: exit 0/2, never traceback or hang. (e) `wave.json` traversal/pid values via `wave status`/`plan` only. Authorization is resolved at dispatch (see section 5). |

## 3. Mocking strategy

Anything probed against a mock below is reported `mocked`, never `verified`.

- **Anthropic API / `claude` CLI**: never call live. Put a stub `claude` first on `PATH` for any probe that reaches `runner.py`/`loop.py` spawns (pattern: `skills/use-sonnet/scripts/test_sonnet_run.sh`). For the `api.anthropic.com` probe in `cli/loop.py`, monkeypatch `urllib.request.urlopen` in-process.
- **`codex`, `gemini`, `copilot`**: use the stub binaries from `skills/use-codex/scripts/codex_run_test_lib.sh` and the gemini test's equivalent; set `AUTOPILOT_DISPATCH_DEPTH` explicitly to probe the recursion guard (exit 3).
- **`claude-plugins` release script**: do not mock, do not run. Wendy reads it only.
- **git**: not mocked. Real throwaway repos under `/tmp`; pass `-c commit.gpgsign=false` and a fixture identity for fixture setup commits. Note `record-store` commits with the operator's global identity/signing config: set `GIT_CONFIG_GLOBAL=/dev/null` plus `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env if signing would prompt.
- **Live loop state in `$R`**: never a probe target. Copy `docs/dev/project-management/autopilot/*` into `/tmp` if a realistic store is needed.

## 4. Authoring assignments

No specialist executes this. Specialists put a proposed test in the finding's `fix` field only; the master authors on a branch after the lanes report.

- Release-gate gap: add `skills/run-autopilot/cli/test_store_tree_legibility.py` to the `[checks] store tree` block of `$R/dev/bin/release-checks` (no new test needed; a gate-coverage pin, if wanted, belongs beside `scripts/test_store_tree_prose.py`).
- Store-verb regressions (walter/heidi findings on `ensure-store`, `dirty`, `record-store`, boundary, lane exclusion): pytest under `$R/skills/run-autopilot/cli/` next to the matching `test_store_*.py` module, runner `uv run --no-project --with pytest python -m pytest -q ...`, and listed explicitly in the `store tree` block.
- Hook security regressions (trudy): pytest beside `$R/hooks/test_guard_push_grammar.py` / `test_guard_push_on_critical.py` or the enforce_prd_location layout tests; wire into the `custody push guard` / `hook registration` blocks.
- CLI journey regressions (exit-code contract): pytest under `$R/skills/run-autopilot/cli/` (pattern `test_lifecycle_cli.py`, `test_enter_cli.py`).
- Release-truth drift (wendy): CHANGELOG fix, no test, unless the drift is a contract (manifest versions must agree), then a pin in the `test_*_prose.py` style.
- Performance (peggy): no durable test; report numbers.

## 5. Pins and vetoes

Authorization: not asserted

## 6. Freshness stamp

- Recon date: 2026-10-03 local (measured 2026-10-02T22:56Z)
- Target HEAD: 1daea55509ef17d8eb7703b905273b15d0bcaa9e
