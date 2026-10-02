# Decision Audit Log: 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1

PRD: `00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1.md`
Started: 2026-09-14T06:00:05Z
Completed: 2026-09-14T06:00:05Z
Autonomous: 8  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: Design 00187: custody folded into do_stall as a site-keyed step with a GC-exempt ledger/custody.jsonl journal behind the PRD marker, git-config locator for repo discovery, exact revert reconciliation at resolve, capture failure pauses the batch (row 1) instead of stalling uncustodied

**Choice**: auto-decide

**Rationale**: 3/3 reviewer dispatches (claude, codex, codex); 2 cardinal sins + 19 blockers fixed in the doc; 13 non-blockers logged in ## Review log; dispatch-3 fixes unverified by a further dispatch (ceiling)

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: Tess probe: default completed-section render exits 12 (missing_from_report) when this PRD's own type=stall record sits in the batch deferred JSON

**Choice**: deferred to batch end as an out-of-scope record in the deferred JSON; task 6 tests seed another PRD's record for the default-section check

**Rationale**: the completeness check is not this task's contract (Surgical changes); a fix belongs in missing_from_report itself

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: SKILL.md Git-push-fails row carries the custody resolve sentence only in the loop-mode cell, contradicting phase-build Handle pending custody and the PRD (loop mode never runs custody resolve); the interactive cell has no pointer

**Choice**: auto-fix via [D1] rework task (prose: move the resolve sentence to the interactive cell, make the loop cell say the denial is closed at the next attended Phase 0; update the prose pins)

**Rationale**: bounded, in-scope prose fix that only adds and relocates sentences (no signature, schema or interface change); verified by reading SKILL.md line 297

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: custody.record_critical swallows the failure reason (except returns 9 with nothing on stderr); guard wrappers with value-taking flags (sudo -u NAME, nice -n 10, env -u VAR) produce a false allow; is_push_like tests the raw quoted segment; _record_stall_custody rebuilds the marker entry record_critical already builds; op_id-less marker entry or journal row raises KeyError instead of CustodyError; multi-line detail breaks notice idempotency; _validate_mirror single-caller wrapper; _stall_range name; unscoped PAUSE pin in test_custody_prose; mirror-stale exit-9 branch untested; custody CLI suites not in release-checks

**Choice**: auto-fix via five [D1] rework tasks grouped by file (prose row, custody.py fail-loud and validation, guard wrappers, records/__main__ dedupe and naming, tests and release-checks)

**Rationale**: every item is Low, or Medium with a clear mechanical or additive fix; the swallowed exit-9 reason, the wrapper false allow and the duplicated entry construction were confirmed by reading custody.py:309, guard_push_on_critical.py:189-192 and records.py:434-440

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: five Low findings discarded with reasons in the settled-decisions ledger: stalled_section live-on-master literal (PRD-mandated), _refresh_block 20-line bound vs parser 22 (design-specified), five range-less test_render_custody pins passing at base (preservation pins by construction), records/custody circular import (design-placed, lazy access), guard worst-case over the 10s hook timeout (documented limit)

**Choice**: discarded; recorded in dev/local/reviews/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-ledger.json

**Rationale**: each is a design- or PRD-mandated shape that the doubt lens itself filed as KNOWN with a written justification

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: Push guard wrapper-operand collision: `env -u git git push` / `sudo -u git git push` unwrap to exe `git` with subcommand `git`, so neither the push check nor the `wrapped and exe != "git"` fallback fires and a push from a guarded cwd is ALLOWED (Bob + Carl, 2/4); and the flag-free wrapper false deny: `command echo 'git' 'push'` is uncertain solely because `wrapped=True`, contradicting the PRD's pass list (Bob, 1/4); plus two redundant asserts in test_git_push_row_routes_a_guard_denial_to_custody_resolve (Bob, 1/4)

**Choice**: swept via one [D2] tail-sweep task (task 13, opus) after convergence: a wrapper that consumed any -flag makes the segment uncertain, a flag-free wrapper classifies its executable normally; drop the row-wide presence and full-sentence loop-exclusion asserts

**Rationale**: both guard behaviours reproduced by the orchestrator with dev/local/tmp/00187-c2-guard-probe.py before deciding (is_push_like False / subcommand 'git' for the bypass; is_push_like True for the false deny); the assert redundancy confirmed by reading test_custody_prose_schema.py:274-294 against _PUSH_DENIAL_SENTENCE. Medium with a clear mechanical fix; no CRITICAL/HIGH remains so the cycle converged and the tail is swept, not dropped

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: custody.marker_entry() built twice with identical inputs in the do_stall step-4b path (inside record_critical and again in records._record_stall_custody)

**Choice**: discarded; recorded in dev/local/reviews/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-ledger.json

**Rationale**: record_critical's keyword-only, int|None signature is the design's verbatim contract; threading the entry means changing that interface to save one pure five-key dict build

### [autonomous] 2026-09-14T06:00:05Z

**Decision**: six fail-first-replay [MECH] rows (19 touched tests reported passing against the pre-change code across test_guard_push_grammar.py, test_guard_push_on_critical.py, test_custody_entry.py, test_custody_loud.py, test_custody_prose.py, test_custody_resolve.py)

**Choice**: discarded with measured reasons in the ledger (one entry per row)

**Rationale**: re-run in a base worktree at 1fda596 with HEAD's test files overlaid: 7 of the 19 FAIL at base (pytest exit 1, SUBFAILED under unittest.subTest, which replay_tests_against_base.py misreads as the parent's PASSED); the other 12 are 8 byte-for-byte moved grammar tests plus the untouched registration test (refactor split), one preservation pin, one tightened pin over unchanged prose and one coverage backfill - each passes at base by construction

### [deferred] 2026-09-14T06:00:05Z

**Decision**: skills/run-autopilot/cli/__main__.py is 1008 lines, over the 800-line file cap (909 at work_start_sha, +99 from this PRD: custody verb, stall-record lookup, _run_render split)

**Choice**: defer to batch end for PRD minting

**Rationale**: pre-existing overflow; the lines this PRD added are design-mandated and removing only them leaves the file over the cap; a per-surface split of __main__.py is its own PRD, as loop.py got under 00192
