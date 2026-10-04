# Decision Audit Log: 00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1

PRD: `00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1.md`
Started: 2026-10-04T12:02:59Z
Completed: 2026-10-04T12:02:59Z
Autonomous: 15  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The rework bullet "head_sha absent -> fall back to a full review (omit --since)" still omits --since, so under autopilot at a clean master HEAD gather-context.sh exits 3 on that path

**Choice**: auto-fix via tail sweep task [D1] B

**Rationale**: 3/4 consensus, highest-agreement finding; mechanical prose fix in the same file the PRD already edits

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: state_path.parents[1] raises an uncaught IndexError when --state is a bare relative filename; the call sits outside the try block

**Choice**: auto-fix via tail sweep task [D1] C

**Rationale**: 2/4 consensus; reproduced independently this cycle (Path('state.json').parents has one element) and confirmed new in commit 6e31e89; mechanical fix (resolve the path)

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The empty-diff probe buffers the whole diff in DIFF_CONTENT just to test emptiness; 2>/dev/null || true makes a failing git diff read as an empty diff; the header comment says nothing is written but mkdir -p runs first

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 2/4 consensus; behavior-preserving simplification plus a fail-loud correction, both bounded to one script

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The new regression tests are not wired into the release gate: test_lane_check.py is absent from the effort-lanes block and test_gather_context_id.sh is not run anywhere

**Choice**: auto-fix via tail sweep task [D1] D

**Rationale**: 2/4 consensus; verified this cycle by rg over dev/bin/release-checks - only test_gather_context_paths.sh is named; a regression test no gate runs cannot catch a regression

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The "--since given, refusal never fires" guard is untested: deleting -z "$SINCE_REF" && leaves every test green

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 1/4 but additive-only (adds a test scenario) and names the exact missing case from the task's own Details

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: test_lane_check.py duplicates an existing harness: _clean_git_env copies test_store_boundary.py and BareRepo re-implements Fixture(bare=True)

**Choice**: auto-fix via tail sweep task [D1] C

**Rationale**: 1/4; de-slop finding with a named existing home (store_tree_testutil.py), behavior-preserving

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The new preflight suppresses Git errors with 2>/dev/null || true, misreporting failed diffs as empty diffs

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 1/4 from the doubt lens; same defect Alice reached from the other side - silently swallowed error, against the project's fail-loud rule

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The preflight materializes the entire patch even with --since, when refusal cannot fire, then regenerates it for the artifact

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 1/4; behavior-preserving efficiency fix bounded to the same guard the other findings touch

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: Bare-store coverage only commits harmless JSON, leaving the security-scan exclusion unpinned

**Choice**: auto-fix via tail sweep task [D1] C

**Rationale**: 1/4; additive test coverage for the security branch of the very function this PRD changed

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: store_tree.STORE_EXCLUDE_PATHSPECS is now unused in production; lane_check.diff_signal was its only consumer

**Choice**: auto-fix via tail sweep task [D1] C

**Rationale**: 1/4; dead code this diff orphaned, so it is the diff's own mess to clean (surgical-changes rule), not pre-existing dead code

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: An invalid or unreachable --since ref fails rev-parse --verify, so DIFF_BASE silently falls back to the branch base and the refusal is skipped because SINCE_REF is non-empty

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 1/4; the remaining silent-empty-review path the PRD's capability title claims to close

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The park_halt row's "otherwise the row matching the exit code detail names" points at rows that cannot exist for an unmapped code

**Choice**: auto-fix via tail sweep task [D1] B

**Rationale**: 1/4; the wording is PRD-verbatim so the prose matches its spec, but the spec itself leaves an unmapped code with no row - a one-line prose addition closes it

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: Style drift: stray space before the comma in next((r for r in rows if _first_cell(r) == "park_halt") , None)

**Choice**: auto-fix via tail sweep task [D1] D

**Rationale**: 1/4; one-character fix in a line this diff added

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: The empty-diff guard keys on -z "$SINCE_REF", not on whether --since took effect; a repo with no detectable base still exits 0 on an empty diff

**Choice**: auto-fix via tail sweep task [D1] A

**Rationale**: 1/4 from the blind lens; same root as the invalid-ref finding, grouped into one task so the guard is rewritten once

### [autonomous] 2026-10-04T12:02:59Z

**Decision**: Cannot statically verify: acceptance suites pass (VERIFY: run pytest -k "enter or lane_check", test_gather_context_id.sh, and dev/bin/release-checks)

**Choice**: discarded - already verified this cycle

**Rationale**: Bob's sandbox cannot execute; all three named commands ran green this cycle (209 passed, 4/4 PASS, release-checks exit 0 with 2268 passed), so the item is answered by evidence rather than by a task

### [deferred] 2026-10-04T12:02:59Z

**Decision**: __main__.py is 1344 lines, over the 800-line limit, and this diff adds 4 more at the diff_signal call site

**Choice**: deferred - settled pre-existing deferral

**Rationale**: Pre-existing and already settled by PRDs 00223, 00236 and 00241; the only line this PRD adds there is the PRD-mandated diff_signal call-site argument. Splitting the CLI dispatcher is a separate PRD, not this PRD's narrow plumbing scope. Drives R13: fail for Alice and Bob; not a regression.

### [deferred] 2026-10-04T12:02:59Z

**Decision**: KNOWN: __main__.py exceeds the 800-line ceiling. This predates the change; splitting the CLI dispatcher is outside this PRD's narrowly scoped plumbing fixes.

**Choice**: deferred - settled pre-existing deferral

**Rationale**: Bob's wording of the same settled deferral as the row above; recorded separately so the ledger matcher can dismiss either phrasing next cycle.
