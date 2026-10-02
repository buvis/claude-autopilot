# Decision Audit Log: 00161-doctor-codex-host-hooks-v1

PRD: `00161-doctor-codex-host-hooks-v1.md`
Started: 2026-09-02T04:18:35Z
Completed: 2026-09-02T04:18:35Z
Autonomous: 5  |  Deferred: 8  |  Doubts: 0

### [autonomous] 2026-09-02T04:18:35Z

**Decision**: Carl (Gemini) unavailable: copilot backend refused model gemini-3.1-pro-preview; native gemini backend returned IneligibleTierError (free tier no longer supported)

**Choice**: auto-fix

**Rationale**: graceful degradation per retry-policy.md - one retry spent on the native backend, then Carl marked unavailable; cycle proceeded with Alice, Blake and Bob

### [autonomous] 2026-09-02T04:18:35Z

**Decision**: PRD internal contradiction: the batch-probe prose requires detail="hook_doctor: <first broken TSV line>" and hook_doctor="<summary line>" for BOTH exit 1 and exit 2, but the Check spec defines exit 2 as an unusable config, where the doctor emits neither a per-target TSV line nor a summary line

**Choice**: auto-fix

**Rationale**: requirements ambiguity resolved by the simplest safe assumption rather than deferred: corrected the PROSE (split the exit-1 and exit-2 mappings so each names a field the doctor actually emits) instead of widening the doctors verdict contract, which the PRD pins verbatim. Doc-only, no behaviour change, reversible. Task 9.

### [autonomous] 2026-09-02T04:18:35Z

**Decision**: consolidate_findings.py listed Blake's "repair() reads hooks.json once" and Bob's "repair snapshots registrations" as two separate [1/3] rows

**Choice**: auto-fix

**Rationale**: same defect, split only because Bob's File carried a :257 line suffix and Blake's did not; merged into one 2/3 finding and routed to a single task (7)

### [autonomous] 2026-09-02T04:18:35Z

**Decision**: Bob (sandboxed) could not statically verify that the acceptance pytest suites and release checks pass

**Choice**: routed to verification

**Rationale**: queued in dev/local/reviews/00161-doctor-codex-host-hooks-v1-checks-1.json as: uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot . No task created. Bob's sibling commands (bash dev/bin/release-checks) and the post-release host check/repair/check step were NOT queued - chained commands and an operator-only step fail the one-command queue shape rule.

### [autonomous] 2026-09-02T04:18:35Z

**Decision**: Blake flagged that test_codex_hook_doctor_repair.py is a third file not listed in the PRD's Repository Structure

**Choice**: auto-fix

**Rationale**: kept the split - the style/line-limit gate mandated it (commit 74f3221). Only the actionable half was tasked: SKILL.md must name both test files so a reader running the PRD's literal Phase 1 acceptance command knows where repair coverage lives. Task 11.

### [deferred] 2026-09-02T04:18:35Z

**Decision**: The verdict-ordering fix creates a repair gap: a known hook now verdicted `syntax_error` is ignored by `_repair_known`, so `repair` emits no action and leaves the exact newly-gated failure broken. Confirmed by the orchestrator against the code: _repair_known returns None for syntax_error (line 171), while _repair_unknown does emit unrepairable for it (line 155) and is reached only when the target is unknown. So a KNOWN syntax-broken hook gets no TSV line and no repair even though its canonical source exists. This is a regression the cycle-1 verdict-ordering fix introduced: such a hook used to verdict stale and be repaired from canonical. Fix: add syntax_error to the _repair_known verdict tuple (repair from canonical when present, else unrepairable) plus a repair regression test.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: Reading source with forced UTF-8 rejects valid Python hooks using another PEP 263 encoding, although `py_compile` would accept them; such hooks are falsely reported `syntax_error` and gate Codex. Confirmed by the orchestrator: line 66 is compile(target.read_text(encoding=utf-8), str(target), exec), which decodes before compiling, so a valid file carrying a PEP 263 coding declaration in another encoding raises UnicodeDecodeError and is verdicted syntax_error (exit 1, rung gates off). The PRD specifies this verdict as py_compile fails, and py_compile honors the coding cookie. Fix: pass target.read_bytes() to compile(), which restores PEP 263 handling and keeps the read-only property the cycle-1 fix was for; add a latin-1 fixture.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: The canonical-source read in _missing_common_import_names only catches `SyntaxError`, not `UnicodeDecodeError`/`OSError` (unlike the sibling loop the same task fixed a few lines above); a non-UTF-8 canonical `_common.py` under the aegis root still aborts the whole `repair` run (exit 2, no TSV output for any target, including healthy ones) instead of reporting that target `unrepairable` and continuing. Alice reproduced it directly; no test exercises it. Highest-consensus finding of the cycle.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: repair() parses `hooks.json` with the identical json.loads(config.read_text(encoding=utf-8))[hooks] expression twice (lines 278 and 297); extracting a small _load_hooks(config) helper would remove the duplication while preserving the deliberate re-read-before-cleanup behavior.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: Exit 2 is documented exclusively as an unreadable config and recorded as `config unreadable`, but the CLI also returns 2 for malformed event entries, command tokenization, unresolved plugin roots, and target I/O failures; those paths are now misdiagnosed in state and reports. Fix direction: either a neutral doctor-error state value, or document the distinct structural, root-resolution and target-I/O mappings.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: The non-UTF-8 sibling regression test accepts any non-error return code and never asserts that `_common.py` was refused and left untouched, so an unsafe rewrite would still pass. Fix: assert exit 1, an unrepairable `_common.py` record, and unchanged `_common.py` bytes.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: _snapshot claims to prove byte-identical read-only behavior but records only paths and sizes; an existing bytecode or config file can be rewritten with the same size without failing the test. Fix: snapshot file bytes plus relevant metadata so same-size rewrites fail.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-02T04:18:35Z

**Decision**: Two newly moved tests still explain multiline `py_compile` diagnostics even though the implementation removed `py_compile`; replace the stale multi-paragraph commentary with the actual one-line compile() contract.

**Rationale**: rework cap reached with this finding unresolved
