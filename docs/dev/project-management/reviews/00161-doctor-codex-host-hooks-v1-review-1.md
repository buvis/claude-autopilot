---
prd: dev/local/prds/wip/00161-doctor-codex-host-hooks-v1.md
review: 1
date: 2026-09-02
head_sha: 4f57b873bd534ba8a00a5aa81ccef9436c9fcead
codex_thread_id: 01a05fb1-d07a-7ac3-ae56-ca7d30427ba3
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
---

# Review: 00161-doctor-codex-host-hooks-v1

Diff range: `0c0c80107c9d297d372ff2429f5cd57af4bd07e8..4f57b873bd534ba8a00a5aa81ccef9436c9fcead`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context, not invalid.

**Diff-scope note (fail-loud).** `gather-context.sh` run without `--since` produced an EMPTY diff: it diffs against the detected base branch, and this repo's current branch *is* `master`, so `git diff master` yields nothing. The context was regenerated with `--since 0c0c8010…`, giving the PRD's whole work range. The context file's own scope label therefore reads "incremental review (changes since 0c0c8010…)" — that label is wrong; this is a **full cycle-1 review** covering every commit of the PRD. 2005 diff lines across 10 files.

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00161-doctor-codex-host-hooks-v1

### Agent Status

- Alice: ✅ Available (consensus lens, `legacy` engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex; consensus + doubt/de-slop lens)
- Carl: ⚠️ Unavailable: copilot backend refused model `gemini-3.1-pro-preview`; retry (1/1) on the native `gemini` backend returned `IneligibleTierError` — "Gemini Code Assist for individuals" no longer supports this client. Graceful degradation per `retry-policy.md`; the cycle ran with three reviewers.

## Consolidated Findings

20 findings. No Critical. Consensus is computed over the 3 reviewers that ran.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/3] | 🟡 Medium | `_probe_line()` leaks a stale batch's `hook_doctor` note onto the "codex probe: not run" line — the `; hooks:` suffix is appended unconditionally after the verdict branch instead of only for a fresh (matching-batch_id) probe | skills/run-autopilot/cli/render_report.py | 2 | ALICE, BOB |
| [2/3] | 🟠 High | `repair` snapshots registrations before repairing targets instead of re-reading immediately before placeholder deletion as required, so a newly registered zero-byte hook can be deleted / `repair()` reads `hooks.json` once at the top and reuses that `registered` set for the placeholder scan rather than re-reading "at that moment" | skills/use-codex/scripts/codex_hook_doctor.py:257 | 3 | BOB, BLAKE |
| [1/3] | 🟠 High | repair() crashes (uncaught FileNotFoundError → generic exit 2) instead of reporting `unrepairable` and continuing, when a known target is missing/empty and its canonical source is also absent — `_repair_known` reads `canonical.read_bytes()` without checking existence | skills/use-codex/scripts/codex_hook_doctor.py | 3 | ALICE |
| [1/3] | 🟠 High | `_missing_common_import_names()` reads every sibling with `.read_text(encoding="utf-8")` and only catches `SyntaxError`; a non-UTF-8 sibling crashes `repair` with an unhandled `UnicodeDecodeError` traceback instead of the tool's own `error: ...`/exit-2 contract | skills/use-codex/scripts/codex_hook_doctor.py | 3 | BLAKE |
| [1/3] | 🟠 High | `check` is not read-only: `py_compile.compile` writes `__pycache__/*.pyc` beside hooks, so a batch can mutate `~/.codex`; use in-memory `compile()` instead | skills/use-codex/scripts/codex_hook_doctor.py:69 | 1 | BOB |
| [1/3] | 🟠 High | Known hooks are compared for staleness before syntax validation, so invalid drifted code returns `stale`/exit 3 and does not gate Codex; validate syntax before comparing canonical bytes | skills/use-codex/scripts/codex_hook_doctor.py:58 | 1 | BOB |
| [1/3] | 🟠 High | `str(PyCompileError)` can contain embedded newlines, violating the one-TSV-line and one-line-detail contracts and breaking first-broken-line parsing | skills/use-codex/scripts/codex_hook_doctor.py:71 | 1 | BOB |
| [1/3] | 🟠 High | Exit 2 emits only stderr and no TSV or summary, while the batch instructions require a first broken TSV line and doctor summary for exits 1 and 2; the exit-2 state protocol is currently impossible to implement as documented | N/A | 4 | BOB |
| [1/3] | 🟠 High | Registered paths are not normalized; a command such as `hooks/../hooks/custom.py` differs from the globbed path, allowing cleanup to delete a registered zero-byte unknown hook | skills/use-codex/scripts/codex_hook_doctor.py:42 | 3 | BOB |
| [1/3] | 🟠 High | Cleanup exempts every `KNOWN_HOOKS` basename and the blanket directory scan repairs them even when unregistered; an unregistered zero-byte `protect_config.py` is rewritten instead of removed as the placeholder contract requires | skills/use-codex/scripts/codex_hook_doctor.py:95 | 3 | BOB |
| [1/3] | 🟡 Medium | Bug-fix commit e9b2a94 (guard against unparseable `_common.py` siblings) ships with no regression test, contrary to the repo's fail-first bug-fix testing rule | skills/use-codex/scripts/codex_hook_doctor.py | 3 | ALICE |
| [1/3] | 🟡 Medium | check() treats every `*.py` file directly in the hooks directory as an implicit target, not just `_common.py` per the PRD's Behavior text — broader than spec, needed in practice for the stated success metric but untested as a deliberate general policy | skills/use-codex/scripts/codex_hook_doctor.py | 1 | ALICE |
| [1/3] | 🟡 Medium | Malformed command or event structures can escape the exit-2 handling: `shlex.split` can raise `ValueError`, and non-mapping entries can raise `AttributeError` | skills/use-codex/scripts/codex_hook_doctor.py:32 | 1 | BOB |
| [1/3] | 🟡 Medium | The two prose pins assert only the ubiquitous substrings `hook_doctor` and `repair`, so they still pass if the required exit mapping, schema shape, or operator-only rule disappears | skills/use-codex/scripts/test_codex_hook_doctor.py:762 | 4 | BOB |
| [1/3] | 🟡 Medium | The new check tests repeat fixture construction, CLI invocation, and comments that restate test names; replace this boilerplate with fixture factories and parametrized verdict cases | skills/use-codex/scripts/test_codex_hook_doctor.py:73 | 1 | BOB |
| [1/3] | 🟡 Medium | The PRD's critical host-shape scenario is missing: no fixture drives all seven known hooks through stale check exit 3, repair, and final check exit 0, and no test pins the exact batch-state mapping | skills/use-codex/scripts/test_codex_hook_doctor.py:663 | general | BOB |
| [1/3] | ⚪ Low | The PRD's Repository Structure lists only two files under `skills/use-codex/scripts/`; the implementation adds `test_codex_hook_doctor_repair.py`, so Phase 1's literal acceptance command no longer exercises any repair-mode scenario | skills/use-codex/scripts/test_codex_hook_doctor_repair.py | 3 | BLAKE |
| [1/3] | ⚪ Low | `repair()` emits no TSV line at all for a KNOWN target verdicted `no_canonical`, unlike an unknown broken target which gets `unrepairable` — an observability gap, not a functional bug | skills/use-codex/scripts/codex_hook_doctor.py | 3 | BLAKE |
| [1/3] | ⚪ Low | Cannot statically verify: acceptance pytest suites, release checks, and the post-release host check/repair/check signal pass | N/A | general | BOB |

**Consolidator correction (recorded, not silent).** `consolidate_findings.py` emitted the re-read-config defect as two separate `[1/3]` rows — Blake's and Bob's — because Bob's `File` cell carried a `:257` line suffix and Blake's did not, and the merge keys on file equality. They are one defect. The table above shows it merged at its true `[2/3]`. Everything else is the script's output unmodified.

## Alice

Ran every acceptance command and reproduced two defects directly rather than reading for them:

- `repair()` aborts with `error: [Errno 2] No such file or directory: '.../aegis_root/hooks/validate_commit_msg.py'` and exit 2 when a known target is `missing`/`empty` and its canonical source is also absent, instead of reporting `unrepairable` for that one target and continuing. `_repair_known` calls `canonical.read_bytes()` with no existence check; the check that exists lives in `_verdict_for`'s `stale`/`no_canonical` branch, which a `missing`/`empty` target never reaches.
- `_probe_line()` renders `codex probe: not run; hooks: stale: _common.py` for a probe carried over from a mismatched `batch_id`. `test_probe_from_another_batch_renders_not_run` uses `assertIn`, so it does not catch the trailing suffix.

Also flagged: commit `e9b2a94` shipped a bug-fix guard with zero regression tests; and `check()`'s implicit-target discovery globs every `*.py` in the hooks directory, which is broader than the PRD's literal `_common.py` wording but is what makes the zero-byte leftovers surface (confirmed by reproduction) — untested as a deliberate policy.

Reported suite results: 39 passed on the two doctor suites, 55 passed on the render suites, 2031 passed / 1 skipped on the full sweep.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens — PRD only, no diff, no file list, no review history. He located the implementation himself and ran every acceptance command literally, plus the full suite (2031 passed, 1 skipped) and `dev/bin/release-checks` (green, `test_codex_run.sh` confirmed untouched via `git log`).

Strongest independent signal this cycle: he ran `codex_hook_doctor.py check` read-only against the real `~/.codex/hooks.json` and it reproduced the PRD's problem statement exactly — 7 `stale`, 2 `empty` (`analyze-instincts.py`, `observe_tool.py`), exit 1. He did not run `repair` against the real `~/.codex`, correctly treating it as operator-only.

His four findings are in the table above. `B14` is his only failing rule.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Consensus + doubt/de-slop lens (codex, static-only sandbox). Twelve findings plus one explicit "cannot statically verify" notice. He is the only reviewer who reached the `check`-writes-bytecode defect, the staleness-before-syntax ordering inversion, and the path-normalization hole.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

### Doubt buckets

FIX:
- Check mode writes bytecode beside hooks — `skills/use-codex/scripts/codex_hook_doctor.py:69` — replace `py_compile.compile` with in-memory compilation and add a no-filesystem-change test.
- Syntax-invalid known hooks can be classified as stale — `skills/use-codex/scripts/codex_hook_doctor.py:58` — perform syntax validation before canonical comparison and test an invalid drifted known hook.
- Syntax details can split TSV records — `skills/use-codex/scripts/codex_hook_doctor.py:71` — normalize diagnostic whitespace to one line and assert exact output shape.
- Exit-2 output cannot populate the documented batch state — `skills/use-codex/scripts/codex_hook_doctor.py:377` — emit a parseable error record and summary, or explicitly specify and test stderr-to-state synthesis.
- Placeholder cleanup uses an early registration snapshot — `skills/use-codex/scripts/codex_hook_doctor.py:257` — re-read `hooks.json` immediately before `_remove_orphaned_empty`.
- Lexically equivalent registered paths can be deleted — `skills/use-codex/scripts/codex_hook_doctor.py:42` — normalize targets without following symlinks before deduplication and membership checks.
- Unregistered known-basename placeholders are repaired rather than removed — `skills/use-codex/scripts/codex_hook_doctor.py:95` — make only registered targets plus `_common.py` implicit and remove other unregistered zero-byte files.
- Old-batch hook notes leak into `not run` reports — `skills/run-autopilot/cli/render_report.py:363` — append the suffix only for a matching batch and add a mismatched-batch regression test.
- Malformed hook structures can traceback — `skills/use-codex/scripts/codex_hook_doctor.py:32` — validate lists/mappings/command strings and convert `ValueError` and `AttributeError` into exit 2.
- Prose pins do not bind to intent — `skills/use-codex/scripts/test_codex_hook_doctor.py:762` — assert the required section, exit mappings, state fields, and operator-only rule.
- Test boilerplate obscures behavior — `skills/use-codex/scripts/test_codex_hook_doctor.py:73` — centralize fixture creation and parametrize equivalent verdict/exit cases.
- Critical multi-hook integration coverage is absent — `skills/use-codex/scripts/test_codex_hook_doctor.py:663` — add the seven-hook stale-to-repaired scenario and exact doctor-to-state contract assertions.

VERIFY:
- Runtime acceptance remains unverified — run `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot`, then `bash dev/bin/release-checks`; after release run host `check`, `repair`, `check` and inspect the next batch report.

KNOWN:
- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

### Verification-check queue

The single VERIFY item was **partially queued** to `dev/local/reviews/00161-doctor-codex-host-hooks-v1-checks-1.json`:

- **Queued** — `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot` (one command, correct shape).
- **Not queued: command shape** — the sibling `bash dev/bin/release-checks` (the VERIFY text chains it with "then"; one entry carries one command) and the post-release host `check`/`repair`/`check` step (operator-only, outside any batch, and the PRD forbids a batch running `repair`). Both are recorded here rather than dropped silently.

Both automated commands were already run green at this exact HEAD — see the `Tests:` line below.

## Carl

⚠️ Unavailable. Not invoked successfully; contributed no findings. Consensus denominators throughout this file are `/3`, not `/4`.

## Follow-up Tasks Created

Seven tasks, ids 5–11, grouped by theme (under the 10-task scope-alarm threshold):

1. `[D1] Check verb: read-only compile, verdict ordering, one-line detail, malformed-config robustness` (M) — 🟠 High ×3 + 🟡 Medium ×1
2. `[D1] Repair: never crash on a missing canonical source or a non-UTF-8 sibling` (S) — 🟠 High ×2, both reproduced
3. `[D1] Repair: re-read config before cleanup, normalize target paths, stop exempting unregistered known basenames` (M) — 🟠 High ×3 (incl. the merged [2/3])
4. `[D1] Report: scope the ; hooks: suffix to a matching-batch probe` (S) — 🟡 Medium [2/3], the cycle's highest-consensus finding
5. `[D1] Batch probe: make the exit-2 state protocol implementable` (S) — 🟠 High, doc-only resolution
6. `[D1] Tests: regression for e9b2a94, intent-binding prose pins, seven-hook host scenario, implicit-target policy` (M) — 🟡 Medium ×4
7. `[D1] Repair: report no_canonical known targets, and note the split repair suite in the docs` (S) — ⚪ Low ×2

One finding created no task by design: Bob's ⚪ "cannot statically verify" is routed to verification (queued above), per the PRD 00164 routing rule.

Verdict: 20 findings
Tests: 2607 passed, 0 failed, 1 skipped (reused from last-verification.json at 4f57b873bd534ba8a00a5aa81ccef9436c9fcead)
