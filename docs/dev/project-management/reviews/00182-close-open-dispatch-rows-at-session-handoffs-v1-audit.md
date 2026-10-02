# Decision Audit Log: 00182-close-open-dispatch-rows-at-session-handoffs-v1

PRD: `00182-close-open-dispatch-rows-at-session-handoffs-v1.md`
Started: 2026-09-07T01:55:46Z
Completed: 2026-09-07T01:55:46Z
Autonomous: 14  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: open_ids and _spans_handoff catch only FileNotFoundError while _queued_at also catches OSError, so an unreadable or undecodable ledger raises out of the handoff verb and breaks the documented rule that a telemetry failure is never a dispatch failure

**Choice**: auto-fix

**Rationale**: confirmed by direct read: except OSError exists at line 91 in _queued_at but is absent at lines 126 and 157. Fix is additive (add the missing except branches plus tests) and changes no signature, type or schema.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: The PRD named acceptance tests were relocated out of test_record_dispatch.py by the style gate, so the PRD own verification commands collect none of them

**Choice**: auto-fix

**Rationale**: confirmed by running the command verbatim: pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids exits 5 with 10 deselected. Fix is mechanical relocation of tests between files and touches no production code.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: _spans_handoff duplicates the read, parse and skip-count loop of _queued_at, so one end call re-reads the same file and prints the skipped-unparseable-line warning twice

**Choice**: auto-fix

**Rationale**: reproduced by Alice on stderr; clear mechanical fix (one shared line reader used by all three scan functions), and it is the natural place to add the missing OSError branch above.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: The resume edge is exercised only with an already-closed row, so a regression that closed open rows on leave alone would still pass

**Choice**: auto-fix

**Rationale**: additive test only; the PRD explicitly requires the resume edge to close rows too, so this is a named behavior left unpinned.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: The row-catalogue table in subagent-dispatch.md still says elapsed_s is null only when no start row exists, and omits that the handoff timestamp must fall strictly between the endpoints

**Choice**: auto-fix

**Rationale**: docs-only correction of a table the PRD Phase 2 task was meant to update; the code implements the strict-between rule at line 140.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: Commit 1f045ca reflows two unrelated spots (the open_ids boolean condition and the --prompt-file argparse call)

**Choice**: discard

**Rationale**: contradicts the attempt record: those wraps are the repo own style gate output (task 2 attempt carries style_gate fixed:0647aa4). Reverting them would re-trip the gate.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: Bob two VERIFY items asking that the full suite and the release gate be run

**Choice**: discard

**Rationale**: already answered at this exact HEAD. last-verification.json at sha 095431e records 895 passed / 0 failed / 0 skipped and release-checks exit 0; Alice, Blake and Carl each ran suites green independently. Bob sandbox blocks execution by design, so these are sandbox limits, not defects. Not queued as verification checks either: output-formats.md reserves source bob and the bob persona defines no VERIFY bucket.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: consolidate_findings.py emitted 13 rows because its same-file merge rule was defeated by the line-number suffix Bob appends to File values (record_dispatch.py vs record_dispatch.py:151)

**Choice**: auto-fix

**Rationale**: corrected by hand at the decision gate: three defects each reported by two reviewers were merged, taking the higher severity, which raised two of them to 2/4 high. Recorded so the merge is visible rather than silent. The underlying script limitation is a separate tooling issue, not a PRD 00182 defect.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: Bob first codex dispatch returned no usable review: the sandbox refused to open the context and diff by path, so he emitted a single cannot-read line and failed all twelve R rules

**Choice**: auto-fix

**Rationale**: transient reviewer failure, handled by the one-retry budget per retry-policy.md. Retried once with a fully inlined 81 KB prompt carrying the context and diff verbatim; the retry produced a complete review with seven findings and all seventeen verdict lines. Logged and continued per the Safety Checks table.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: gather-context.sh produced an empty diff because its branch-base detection picked master, which is the branch this PRD work was committed onto

**Choice**: auto-fix

**Rationale**: re-ran with --since state.work_start_sha, which is the base the skill mandates for a full review under autopilot, yielding the correct 1328-line diff. The scope label the script then wrote said incremental, so it was corrected in the context file to say full review. Tooling gap in the script, surfaced for the batch report rather than fixed inside PRD 00182.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: Pat raised a LOW on task 6: test_handoff_closes_open_rows_as_lost and the new test_handoff_resume_closes_open_rows_as_lost differ only in the edge string, and could collapse into one parametrized test saving about 35 duplicated lines

**Choice**: noted, not applied

**Rationale**: LOW findings are note-and-proceed per the step-5.7 ladder. Acting on it would restructure test_handoff_closes_open_rows_as_lost, which PRD 00182 names by hand as an acceptance test, immediately after task 6 existed precisely to stop those named tests moving around. The duplication is 35 lines in a test file; the risk is to the PRD acceptance surface. Recorded so the simplification is not lost.

### [autonomous] 2026-09-07T01:55:46Z

**Decision**: The bare repo-wide suite command uv run --no-project --with pytest python -m pytest exits 2 at collection: skills/run-autopilot/scripts/tracon/test_panels.py, test_screens.py and test_stream.py all fail to import with ModuleNotFoundError: No module named rich

**Choice**: auto-fix

**Rationale**: Pre-existing environment gap, not a regression: git log over 9d3e3a1..HEAD for skills/run-autopilot/scripts/tracon/ is empty, so PRD 00182 never touched those files. The bare invocation supplies only pytest, while tracon needs rich and textual. Ran the step-7 suite as uv run --no-project --with pytest --with rich --with textual python -m pytest -q instead, which collects everything and gives the honest full-suite number: 2665 passed, 1 skipped, 459 subtests, exit 0. Surfaced for the batch report rather than fixed inside this PRD, whose scope is record_dispatch.py and its docs.

### [autonomous] 2026-09-07T01:55:46Z

### [autonomous] 2026-09-07T01:55:46Z
