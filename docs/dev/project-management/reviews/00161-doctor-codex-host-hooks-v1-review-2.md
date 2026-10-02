---
prd: dev/local/prds/wip/00161-doctor-codex-host-hooks-v1.md
review: 2
date: 2026-09-02
head_sha: 8b395097b241c1f87681bfd75b15e480b6b33b51
codex_thread_id: 01a05fb1-d07a-7ac3-ae56-ca7d30427ba3
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
---

# Review: 00161-doctor-codex-host-hooks-v1

Diff range: `4f57b873bd534ba8a00a5aa81ccef9436c9fcead..8b395097b241c1f87681bfd75b15e480b6b33b51`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in `/Users/bob/.config/gita/repos.csv`"). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context, not invalid.

**Scope.** Incremental review of the cycle-1 rework only: 21 commits, 1745 diff lines across 11 files. `gather-context.sh` was run with `--since 4f57b873…`; without it this repo produces an EMPTY diff, because the current branch *is* `master` and the script diffs against the detected base branch. Bob resumed his cycle-1 codex thread (`--resume-thread 01a05fb1…`).

## Review Summary

Reviewed: 11 completed tasks (4 original build + 7 cycle-1 `[D1]` rework)
PRDs checked: 00161-doctor-codex-host-hooks-v1

### Agent Status

- Alice: ✅ Available (consensus lens, `legacy` engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (codex; consensus + doubt/de-slop lens, resumed cycle-1 thread)
- Carl: ⚠️ Unavailable: Gemini outage recorded in cycle 1 (copilot backend refused `gemini-3.1-pro-preview`; the native `gemini` backend returned `IneligibleTierError`). The one-retry budget was spent in cycle 1; it was not re-spent here. Graceful degradation per `retry-policy.md`.

Consensus is computed over the 3 reviewers that ran.

## Cycle-1 findings: all 20 verified resolved

Alice re-checked every cycle-1 finding against the current code and its regression tests, and found all 18 code-affecting ones closed (the two remaining were the accepted test-split note and the statically-unverifiable suite claim, both settled at cycle-1 close). Blake, reviewing blind, found no spec gap at all. Nothing from cycle 1 reappears below; every finding in this cycle's table is new.

## Consolidated Findings

8 findings. No Critical. 2 High, 6 Medium.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/3] | 🟡 Medium | `_missing_common_import_names()`'s canonical-source read only catches `SyntaxError`, not `UnicodeDecodeError`/`OSError` (unlike the sibling loop the same task fixed a few lines above); a non-UTF-8 canonical `_common.py` under the aegis root still aborts the whole `repair` run (exit 2, no TSV output for any target, including healthy ones) instead of reporting that target `unrepairable` and continuing — reproduced directly, untested | skills/use-codex/scripts/codex_hook_doctor.py:138 | 6 | ALICE, BOB |
| [1/3] | 🟠 High | The verdict-ordering fix creates a repair gap: a known hook now verdicted `syntax_error` is ignored by `_repair_known`, so `repair` emits no action and leaves the exact newly-gated failure broken. | skills/use-codex/scripts/codex_hook_doctor.py:171 | 5 | BOB |
| [1/3] | 🟠 High | Reading source with forced UTF-8 rejects valid Python hooks using another PEP 263 encoding, although `py_compile` would accept them; such hooks are falsely reported `syntax_error` and gate Codex. | skills/use-codex/scripts/codex_hook_doctor.py:66 | 5 | BOB |
| [1/3] | 🟡 Medium | `repair()` parses `hooks.json` with the identical `json.loads(config.read_text(encoding="utf-8"))["hooks"]` expression twice (lines 278 and 297); extracting a small `_load_hooks(config)` helper would remove the duplication while preserving the deliberate re-read-before-cleanup behavior | skills/use-codex/scripts/codex_hook_doctor.py:278 | 7 | ALICE |
| [1/3] | 🟡 Medium | Exit 2 is documented exclusively as an unreadable config and recorded as `config unreadable`, but the CLI also returns 2 for malformed event entries, command tokenization, unresolved plugin roots, and target I/O failures; those paths are now misdiagnosed in state and reports. | skills/work/references/codex-implementor.md:74 | 9 | BOB |
| [1/3] | 🟡 Medium | The non-UTF-8 sibling regression test accepts any non-error return code and never asserts that `_common.py` was refused and left untouched, so an unsafe rewrite would still pass. | skills/use-codex/scripts/test_codex_hook_doctor_repair.py:646 | 6 | BOB |
| [1/3] | 🟡 Medium | `_snapshot` claims to prove byte-identical read-only behavior but records only paths and sizes; an existing bytecode or config file can be rewritten with the same size without failing the test. | skills/use-codex/scripts/test_codex_hook_doctor.py:68 | 5 | BOB |
| [1/3] | 🟡 Medium | Two newly moved tests still explain multiline `py_compile` diagnostics even though the implementation removed `py_compile`; replace the stale multi-paragraph commentary with the actual one-line `compile()` contract. | skills/use-codex/scripts/test_codex_hook_doctor_extra.py:206 | 5 | BOB |

Consolidation ran through `consolidate_findings.py` with no ledger flags (no ledger file existed at cycle-2 start). Its paraphrase merger folded Alice's and Bob's independent statements of the canonical-`_common.py` defect into the single `[2/3]` row, unmodified.

**Both High findings were reproduced against the code by the orchestrator before classification**, not taken on the reviewer's word:

- `codex_hook_doctor.py:171` — `_repair_known` returns `None` for `syntax_error`, and `_repair_unknown` (which *does* emit `unrepairable` for it, line 155) is reached only when the target is unknown. So a **known** syntax-broken hook gets no TSV line and no repair, although its canonical source sits right there. This is a regression the cycle-1 verdict-ordering fix introduced: a drifted-and-broken known hook used to verdict `stale` and be repaired from canonical; it now verdicts `syntax_error` and is silently skipped. It is the same asymmetry cycle 1 closed for `no_canonical` (task 11), one verdict over.
- `codex_hook_doctor.py:66` — `compile(target.read_text(encoding="utf-8"), …)` decodes as UTF-8 before compiling, so a valid Python file carrying a PEP 263 coding declaration in another encoding raises `UnicodeDecodeError` and is reported `syntax_error`, exit 1, gating codex for the batch. The PRD specifies this verdict as "`py_compile` fails", and `py_compile` honors the coding cookie. Passing bytes to `compile()` restores PEP 263 handling while keeping the read-only property the cycle-1 fix was for.

## Alice

Ran the cycle-1 queued verification command herself: 2052 passed, 1 skipped (pre-existing, unrelated golden-transcript fixture in `skills/work/scripts/test_check_build_overhead.py`), 459 subtests passed.

Confirmed all 18 code-affecting cycle-1 findings resolved, each against the current code *and* its named regression test (`test_hook_doctor_from_another_batch_does_not_leak_into_probe_line`, `test_repair_keeps_a_registered_zero_byte_file_reached_through_an_indirect_command_path`, `test_repair_removes_an_unregistered_zero_byte_file_even_though_its_basename_is_a_known_hook`, `test_repair_reports_unrepairable_for_a_known_target_verdicted_no_canonical_and_cli_exits_3`, `test_repair_full_cycle_recovers_all_seven_known_hooks_from_a_stale_host_state`). The two settled cycle-1 decisions were not re-raised.

Reproduced the canonical-`_common.py` gap directly:

```
repair() with aegis_root/hooks/_common.py containing b'\xff\xfe\x00bad\n'
Direct call: UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff ...  (uncaught)
Via CLI:     exit 2, stdout '', stderr "error: 'utf-8' codec can't decode byte 0xff ..."
```

Through the CLI there is no traceback (`main()`'s `ValueError` net catches it, since `UnicodeDecodeError` subclasses `ValueError`), but the whole repair run is discarded — zero TSV lines even for unrelated healthy targets — instead of reporting `_common.py` `unrepairable` and continuing, which is the contract task 6 established for the sibling case and which the CHANGELOG's own wording implies.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

`[BLAKE] ✅ No issues found`

Blind (PRD-only). Located the implementation himself and ran every acceptance command in the PRD rather than reading for them:

- `pytest -q skills/use-codex/scripts` → 59 passed
- `pytest -q skills/use-codex/scripts/test_codex_hook_doctor.py` (Phase 0 acceptance) → 22 passed
- `codex_hook_doctor.py check --config /nonexistent/hooks.json` → exit 2 (Phase 0 acceptance)
- `pytest -q skills/run-autopilot/cli/test_render.py skills/run-autopilot/scripts/test_golden_contracts.py` → 56 passed
- `pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot` (Phase 2 acceptance) → 2052 passed, 1 skipped
- `rg -n "hooks.json" skills/use-codex/scripts/codex_hook_doctor.py` → only reads, no write call (Phase 1 acceptance)
- `rg -n "config\.toml"` in the doctor → no hits (out-of-scope item confirmed absent)
- Both doc-pin `rg` acceptance commands hit in both files each
- `test_codex_run.sh` last touched 2026-08-25, before this PRD's range — untouched as the Phase 2 exit criteria require
- `KNOWN_HOOKS` matches the spec's basename→canonical list verbatim (7 entries)
- CHANGELOG has the three required `**use-codex**` / `**work**` / `**run-autopilot**` entries under `[Unreleased]`

Two nuances he surfaced explicitly as non-failures: `check()`'s implicit-target scan is broader than the PRD's literal `_common.py` wording, but is documented in `SKILL.md` and pinned by tests, so it reads as a disclosed interpretation rather than scope creep; and the exit-1/exit-2 prose split (`34f9a72`) is the only coherent resolution of a spec text that is internally impossible on the exit-2 path.

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
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Resumed his cycle-1 codex session, so his findings are stated against his own prior critique. Seven findings: two High, five Medium. Consensus rubric:

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

### Doubt lens buckets

```
FIX:
- Known syntax-broken hooks cannot be repaired — skills/use-codex/scripts/codex_hook_doctor.py:171 — repair from a valid canonical source when available, otherwise emit `unrepairable`, and add a syntax-error repair regression.
- Valid non-UTF-8 Python is misclassified — skills/use-codex/scripts/codex_hook_doctor.py:66 — compile source bytes so Python honors PEP 263 encoding declarations and add a Latin-1 fixture.
- Canonical `_common.py` decoding and I/O errors escape targeted handling — skills/use-codex/scripts/codex_hook_doctor.py:138 — use encoding-aware parsing and classify `UnicodeDecodeError`/`OSError` as an unrepairable compatibility check.
- Exit-2 diagnostics mislabel non-config failures — skills/work/references/codex-implementor.md:74 — use a neutral doctor-error state value or document distinct structural, root-resolution, and target-I/O mappings.
- Non-UTF-8 sibling test does not pin safety intent — skills/use-codex/scripts/test_codex_hook_doctor_repair.py:646 — assert exit 1, an `unrepairable` `_common.py` record, and unchanged `_common.py` bytes.
- Read-only snapshot compares sizes rather than contents — skills/use-codex/scripts/test_codex_hook_doctor.py:68 — snapshot file bytes plus relevant metadata so same-size rewrites fail.
- Test commentary refers to removed `py_compile` behavior — skills/use-codex/scripts/test_codex_hook_doctor_extra.py:206 — replace both stale explanations with concise `compile()`-based contract comments.
VERIFY:
- (none)
KNOWN:
- (none)
```

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

The VERIFY bucket is empty, so `dev/local/reviews/00161-doctor-codex-host-hooks-v1-checks-2.json` is an empty array — no verification checks are queued for this cycle. The cycle-1 queue (`checks-1.json`) recorded `exit 0`, so nothing is carried forward as a finding.

## Follow-up Tasks Created

See `dev/local/autopilot/state.json` — the decision gate creates the `[D2]` rework tasks from the findings above.

Verdict: 8 findings
Tests: 2429 passed, 0 failed, 1 skipped (reused from last-verification.json at 8b395097b241c1f87681bfd75b15e480b6b33b51)
