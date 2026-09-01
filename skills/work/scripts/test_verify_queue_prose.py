"""Prose pins for the verification-check queue and the recorded verification
result (PRD 00164).

Both are file contracts between two skills: `review-work-completion` writes the
queue and reads the record, `work` step 7 reads the queue and writes the record.
Nothing executes either contract but a reader, so the prose is the whole
mechanism - and a contract whose two halves drift apart fails silently, with the
review re-running a suite the work phase already ran and a queued check never
running at all. Hence one file pinning both ends, rather than a pin per skill.

Same pattern as test_dispatch_prose.py: read each file once, assert on short,
reword-resistant substrings, each with a failure message naming what drifted.
Separate file because test_dispatch_prose.py is near the pack's own 800-line
style limit.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_WORK = _SCRIPTS.parent
_SKILLS = _WORK.parent
_FINAL_VERIFICATION = _WORK / "references" / "final-verification.md"
_PHASE_REVIEW = _SKILLS / "run-autopilot" / "references" / "phase-review.md"
_REVIEW = _SKILLS / "review-work-completion"
_OUTPUT_FORMATS = _REVIEW / "references" / "output-formats.md"
_REVIEW_SKILL = _REVIEW / "SKILL.md"

_WORK_SKILL = _WORK / "SKILL.md"

_QUEUE_PATH = "{prd-stem}-checks-{cycle}.json"
_RECORD_PATH = "last-verification.json"


def test_step_7_names_both_sections_it_has_to_run() -> None:
    # SKILL.md is what a work phase reads first; the reference file is read
    # because SKILL.md sends it there. Lose these two names and both procedures
    # sit in a file nobody is told to act on, with every other test still green.
    skill = _WORK_SKILL.read_text()

    assert _RECORD_PATH in skill, (
        "work/SKILL.md step 7 no longer names last-verification.json, so "
        "nothing tells the phase to write the record the review reads."
    )
    assert "verify_check" in skill, (
        "work/SKILL.md step 7 no longer names the verify_check report line, so "
        "the queued checks have no stated call site."
    )


def test_the_queue_file_contract_names_its_path_and_its_shape() -> None:
    formats = _OUTPUT_FORMATS.read_text()

    assert "## Verification-check queue" in formats, (
        "output-formats.md has no '## Verification-check queue' section. It is "
        "the only definition of the file work step 7 reads; without it the "
        "writer and the reader agree on nothing."
    )
    assert _QUEUE_PATH in formats, (
        f"output-formats.md no longer states the queue path {_QUEUE_PATH!r}. "
        "The cycle suffix is load-bearing: one file per cycle is what stops a "
        "stale check from re-running against a later HEAD."
    )
    # "file" included: it is what the issue-text-plus-file matcher compares, so
    # dropping it from the contract silently breaks both readers' matching.
    for field in ('"finding"', '"file"', '"command"', '"source"', '"result"'):
        assert field in formats, (
            f"output-formats.md dropped the {field} key from the queue entry "
            "shape. Every field has one consumer: finding matches the Phase 5 "
            "VERIFY row, command is what runs, source names the lens, result is "
            "what the work phase writes back."
        )


def test_a_verify_finding_without_an_exact_command_is_not_queued() -> None:
    # The queue is for runnable checks. Drop this rule and a vague "look into
    # X" lands in the queue as an unrunnable command, where it either breaks
    # step 7 or is silently dropped - instead of staying a normal finding that
    # rubric rule D3 already fails.
    formats = _OUTPUT_FORMATS.read_text()

    assert "no exact command is NOT queued" in formats, (
        "output-formats.md lost the rule that a VERIFY finding yielding no "
        "exact command stays a normal finding instead of becoming a queue entry."
    )
    assert "D3" in formats, (
        "output-formats.md no longer names rubric rule D3 as what already "
        "catches a vague VERIFY item, which is why the queue may refuse it "
        "rather than inventing a second enforcement path."
    )


def test_an_absent_queue_file_is_never_an_error() -> None:
    # A first-pass build phase has no review behind it. If an absent file ever
    # reads as a fault, every green first build starts reporting one.
    formats = _OUTPUT_FORMATS.read_text()

    assert "absent queue file means no checks" in formats, (
        "output-formats.md lost the reader-tolerance rule. An absent queue file "
        "must mean no checks, never an error."
    )


def test_the_queued_checks_run_inside_the_one_mandatory_pass() -> None:
    # The whole saving is that these run where a suite already runs. Move them
    # anywhere else and the duplicate execution PRD 00164 removed comes back.
    verification = _FINAL_VERIFICATION.read_text()

    assert "## Queued verification checks" in verification, (
        "references/final-verification.md has no '## Queued verification "
        "checks' section, so nothing reads the queue and every VERIFY finding "
        "goes back to being its own rework task."
    )
    assert "verify_check: <command> -> exit <n>" in verification, (
        "references/final-verification.md lost the verify_check report line "
        "shape. The line IS the preserved evidence - a check that ran and was "
        "never reported is indistinguishable from one that never ran."
    )
    assert "Absent queue file" in verification, (
        "references/final-verification.md lost the absent-file no-op, which is "
        "what keeps a first-pass build phase unchanged."
    )


def test_a_failed_queued_check_is_evidence_not_a_phase_failure() -> None:
    # A queued check answers a doubt; it is not a gate. If a red one could fail
    # the phase, the review would be handing the build phase a veto it never
    # had, and step 7's regression loop would start chasing findings.
    verification = _FINAL_VERIFICATION.read_text()

    assert "non-zero exit is evidence, not a phase failure" in verification, (
        "references/final-verification.md no longer says a queued check's "
        "non-zero exit is evidence rather than a phase failure."
    )
    assert "exit timeout" in verification, (
        "references/final-verification.md lost the timed-out queued check's "
        "report value. A check that blew its budget must never be reported "
        "with a passing exit code."
    )


def test_the_review_writes_the_queue_it_alone_can_fill() -> None:
    # The work phase reads the queue but cannot write it: only the review sees
    # the doubt lenses' VERIFY buckets. Drop this and the reader runs forever
    # against a file nothing produces.
    review = _REVIEW_SKILL.read_text()

    assert "verification-check queue" in review, (
        "review-work-completion/SKILL.md step 6 no longer writes the "
        "verification-check queue, so no VERIFY finding ever reaches the work "
        "phase that runs it."
    )
    assert "-checks-<state.cycle>.json" in review, (
        "review-work-completion/SKILL.md no longer names the queue path it "
        "writes. The path is the whole contract with work step 7."
    )
    assert "VERIFY" in review, (
        "review-work-completion/SKILL.md no longer names the VERIFY bucket as "
        "the queue's input, leaving the writer without a source."
    )


def test_the_tests_line_reuse_is_gated_on_the_sha_and_says_which_path_ran() -> None:
    # Both halves matter. Without the sha gate the review reports counts from a
    # different tree; without the provenance suffix a reused count is
    # indistinguishable from a fresh run, which is the failure that makes the
    # whole reuse untrustworthy.
    review = _REVIEW_SKILL.read_text()

    assert "run no suite" in review, (
        "review-work-completion/SKILL.md lost the instruction to skip the suite "
        "on a matching record - the duplicate run PRD 00164 removed is back."
    )
    assert "`sha` equals this cycle's reviewed HEAD" in review, (
        "review-work-completion/SKILL.md no longer gates the reuse on an exact "
        "sha match, so a record from an earlier HEAD could report green over "
        "changed code."
    )
    assert "reused from last-verification.json" in review, (
        "review-work-completion/SKILL.md lost the provenance suffix naming the "
        "reused record. A reused count must never read as a fresh run."
    )
    assert "takes **no** suffix" in review, (
        "review-work-completion/SKILL.md no longer excludes the docs-only form "
        "from the provenance suffix. `cli/gate.py` TESTS_RE admits a suffix "
        "after the counts but none after 'none (docs-only)', so suffixing that "
        "form fails check_review_file.py."
    )


def test_a_queued_finding_creates_no_task_and_is_recorded_anyway() -> None:
    # Both halves are the point. No task is the saving; the autonomous_decisions
    # record is what keeps a check that never ran - a cycle that queues and then
    # converges - visible in the batch report instead of silently dropped.
    phase_review = _PHASE_REVIEW.read_text()

    assert "routed to verification" in phase_review, (
        "phase-review.md Phase 5 has no 'routed to verification' row, so a "
        "queued VERIFY finding falls back to becoming an implementation task "
        "whose work pass re-runs the same suite."
    )
    assert "checks-{cycle}.json" in phase_review, (
        "phase-review.md no longer names the queue file the VERIFY row matches "
        "findings against."
    )
    assert "creates no task" in phase_review, (
        "phase-review.md no longer states that a routed finding creates no "
        "task - the duplicate suite run comes straight back."
    )
    # Row-unique: a bare `autonomous_decisions` also appears in three other
    # paragraphs of this file, so pinning the term alone stays green even if the
    # whole recording clause - the sole mitigation for an unrun check - is cut.
    assert (
        "Record it in `autonomous_decisions` as `routed to verification`"
        in phase_review
    ), (
        "phase-review.md no longer records the routing in autonomous_decisions, "
        "so a queued check that never runs leaves no trace in the batch report."
    )


def test_routing_changes_neither_convergence_nor_any_lens() -> None:
    # This PRD removes a duplicate execution, not a review. Without these two
    # sentences the row reads as licence to converge over open VERIFY items or
    # to drop a lens, which is the thinning the plan forbids.
    phase_review = _PHASE_REVIEW.read_text()

    assert "neither blocks convergence nor suppresses one" in phase_review, (
        "phase-review.md lost the rule that a queued check does not affect the "
        "convergence test in either direction."
    )
    assert "none is removed, skipped or narrowed" in phase_review, (
        "phase-review.md lost the statement that every lens still runs. The "
        "routing row must never read as permission to thin the panel."
    )


def test_the_tail_sweep_does_not_re_task_a_routed_finding() -> None:
    # The sweep is the other path to a task. Excluded in the row but not in the
    # sweep, a routed Medium/Low would be swept into the very [D{cycle}] task
    # the routing exists to avoid.
    phase_review = _PHASE_REVIEW.read_text()

    assert "findings routed to verification (their check runs in step 7" in (
        phase_review
    ), (
        "phase-review.md Tail sweep § Select no longer excludes findings routed "
        "to verification, so the sweep re-creates the task the VERIFY row "
        "declined to create."
    )


def test_zero_tasks_is_delivered_where_tasks_are_actually_created() -> None:
    # Phase 5's routing row runs AFTER review step 7 has already called
    # task-add, so the row alone cannot deliver the PRD's "zero tasks". The
    # exclusion has to live in step 7 as well, or an all-VERIFY cycle still
    # creates the rework task whose work pass re-runs the whole suite.
    review = _REVIEW_SKILL.read_text()

    assert "Skip every finding this cycle queued for verification" in review, (
        "review-work-completion/SKILL.md step 7 no longer skips queued findings, "
        "so it creates the task Phase 5 then declines to create - and step 7 "
        "runs first, so the task wins."
    )
    assert "CRITICAL or HIGH is not skipped" in review, (
        "review-work-completion/SKILL.md step 7 no longer exempts CRITICAL and "
        "HIGH from the skip. They are never routed, so they must keep getting "
        "their task."
    )


def test_a_critical_or_high_is_never_routed() -> None:
    # Without this bound the row collides with the invariant above it ("every
    # CRITICAL lands in deferred_decisions the cycle it is raised") and with the
    # convergence test, and a CRITICAL could finalize with its check unrun.
    phase_review = _PHASE_REVIEW.read_text()

    assert "A CRITICAL or HIGH is never routed" in phase_review, (
        "phase-review.md lost the severity bound on the routing row. A routed "
        "CRITICAL bypasses deferred_decisions and can converge unresolved."
    )
    assert "Medium and Low only" in phase_review, (
        "phase-review.md's routing row no longer states which severities it "
        "covers, which is what makes 'never blocks convergence' true rather "
        "than a contradiction."
    )


def test_routing_matches_on_judgment_not_verbatim_text() -> None:
    # consolidate_findings.py folds paraphrases onto the first-seen wording, so
    # a verbatim match fails precisely on the multi-reviewer findings - the
    # duplicate task returns exactly where consensus is highest.
    phase_review = _PHASE_REVIEW.read_text()

    # Pin the row-unique sentence, NOT "judgment call on issue text plus file":
    # the pre-existing Cap-check paragraph carries that exact phrase, so a pin
    # on it stays green with the routing row's matching rule deleted.
    assert "Match on the entry's `finding` and `file`" in phase_review, (
        "phase-review.md's routing row no longer matches findings the way the "
        "Cap check matches settled deferrals. Verbatim identity misses every "
        "paraphrased consensus finding."
    )
    review = _REVIEW_SKILL.read_text()
    assert "the same way Phase 5 does" in review, (
        "review-work-completion/SKILL.md step 7 no longer states how to match a "
        "row to a queue entry. Phase 5's matching rule runs after task "
        "creation, so a semantic rule there does not help the skip here."
    )
    # Both readers must name the SAME key pair. Divergent matchers let step 7
    # skip a row Phase 5 then fails to match, sending it back through
    # classification into the duplicate rework task this mechanism removes.
    assert "against the entry's `finding` and `file`" in review, (
        "review-work-completion/SKILL.md step 7 matches on a different key pair "
        "than phase-review.md's routing row. One reader skipping what the other "
        "re-tasks is worse than neither doing it."
    )


def test_a_failed_check_has_a_reader_in_the_next_cycle() -> None:
    # "Comes back through the normal path" was a phrase with no mechanism: the
    # result field was written and never read anywhere.
    review = _REVIEW_SKILL.read_text()
    phase_review = _PHASE_REVIEW.read_text()

    assert "Carry the previous cycle's failed checks forward" in review, (
        "review-work-completion/SKILL.md no longer reads the previous cycle's "
        "queue, so a red check is written to a file nothing reads and the next "
        "cycle converges over it."
    )
    assert "`result.exit`" in review, (
        "review-work-completion/SKILL.md no longer names the field that decides "
        "which prior-cycle entries become findings."
    )
    assert "verify-escape" in phase_review, (
        "phase-review.md lost the sweep-path sink. The tail sweep runs step 7 "
        "after convergence and Phase 5 never reopens, so a red check there has "
        "no next cycle and must be deferred to batch end."
    )


def test_the_carry_forward_runs_before_the_verdict_is_counted() -> None:
    # Ordering is the whole correctness of the carry-forward. Composed first,
    # the Verdict line says "converged" over a table that then grows a
    # carried-forward red check - the exact outcome the mechanism prevents.
    review = _REVIEW_SKILL.read_text()

    carry = review.index("**Carry the previous cycle's failed checks forward.**")
    verdict = review.index("**Compose the `Verdict:` line.**")
    assert carry < verdict, (
        "review-work-completion/SKILL.md composes the Verdict line before the "
        "carry-forward adds its findings, so the count excludes them and a "
        "cycle whose only findings are carried forward reads as converged."
    )
    assert "including any findings the carry-forward above just added" in review, (
        "review-work-completion/SKILL.md no longer says the consolidated count "
        "includes the carried-forward findings, so the ordering above is a "
        "coincidence rather than a stated rule."
    )


def test_only_an_integer_zero_counts_as_a_passing_check() -> None:
    # Enumerating failure values is how "refused" got dropped from both readers:
    # a refused check is one step 7 already skipped the task for, so losing it
    # loses the finding entirely. Test for the pass value instead.
    review = _REVIEW_SKILL.read_text()
    phase_review = _PHASE_REVIEW.read_text()
    formats = _OUTPUT_FORMATS.read_text()

    assert "anything but the integer `0`" in review, (
        "review-work-completion/SKILL.md's carry-forward enumerates failure "
        "values again. A `refused` or unrun entry then silently disappears."
    )
    assert 'any exit that is not the integer `0`' in phase_review, (
        "phase-review.md's verify-escape catches only a non-zero exit, so a "
        "timed-out or refused check finalizes unrecorded."
    )
    assert "Only the integer `0` is a pass" in formats, (
        "output-formats.md no longer states the pass value, leaving each reader "
        "to enumerate the failure values and miss one."
    )


def test_the_verify_escape_record_carries_issue_text() -> None:
    # cli/render_report.py missing_from_report: "An item without issue text is
    # always missing" - it fails loud rather than being dropped. So an
    # issue-less verify-escape halts the finalize the record exists to permit.
    phase_review = _PHASE_REVIEW.read_text()

    assert '"issue": "queued check failed:' in phase_review, (
        "phase-review.md's verify-escape record lost its issue field. Phase 9's "
        "reconciliation treats an issue-less open item as always missing and "
        "stops the finalize."
    )
    assert "The `issue` field is not optional" in phase_review, (
        "phase-review.md no longer says why the issue field is mandatory, so "
        "the next edit drops it again."
    )


def test_a_docs_only_diff_is_decided_before_the_record_is_read() -> None:
    # In this pack the work phase always runs and records a suite, so a
    # prose-only PRD has a matching record. Read the record first and the
    # docs-only sentinel is silently replaced by counts. Compare positions, not
    # mere presence: the phrase can survive while the record read moves above it.
    review = _REVIEW_SKILL.read_text()

    assert "Check docs-only first" in review, (
        "review-work-completion/SKILL.md no longer orders the docs-only test "
        "before the record read, so a docs-only review reports suite counts."
    )
    docs_only = review.index("Check docs-only first")
    record_read = review.index("read `dev/local/autopilot/last-verification.json` first")
    assert docs_only < record_read, (
        "review-work-completion/SKILL.md reads the verification record before "
        "deciding docs-only, so a prose-only review silently replaces "
        "`Tests: none (docs-only)` with the work phase's suite counts."
    )


def test_queued_checks_run_once_at_the_settled_head() -> None:
    # Same staleness class the record's null-counts rule closes, and the queue
    # carries no sha, so nothing downstream can detect a stale result. Running
    # before the failure loop and again after would also execute every check
    # twice, against a contract that says each command runs once.
    verification = _FINAL_VERIFICATION.read_text()

    assert "Run these once, at the settled HEAD" in verification, (
        "references/final-verification.md no longer defers the queued checks "
        "until the regression loop resolves, so their results belong to a "
        "pre-fix HEAD with nothing to reveal it - or each check runs twice."
    )


def test_the_rules_that_only_prose_carries_are_each_pinned() -> None:
    # Every clause here is a rule with no runtime behind it, added in a rework
    # and caught by a reviewer. An unpinned sentence is how the last two of them
    # drifted; this is the backstop for that class.
    verification = _FINAL_VERIFICATION.read_text()
    formats = _OUTPUT_FORMATS.read_text()
    phase_review = _PHASE_REVIEW.read_text()

    for text, needle, what in (
        (formats, "no embedded newline", "the writer's newline-is-chaining rule"),
        (
            verification,
            "no embedded newline",
            "the runner's newline-is-chaining rule",
        ),
        (
            formats,
            "not queued: command shape",
            "the writer-side refusal note that keeps a refusal visible",
        ),
        (
            formats,
            "the **runner's** value",
            "the line separating a runner-declined entry from one never queued",
        ),
        (
            phase_review,
            "converges with no work pass leaves its checks unrun",
            "the stated limitation for a cycle that runs no work phase",
        ),
    ):
        assert needle in text, (
            f"{what} is gone. It is prose-only, so nothing else fails when it "
            "drops out - which is exactly how the earlier drift happened."
        )


def test_a_queued_command_is_treated_as_untrusted_input() -> None:
    # The command text is composed by a reviewer from the diff and the PRD, and
    # step 7 would otherwise run it verbatim. Both ends state the constraint:
    # the writer refuses to queue it, the runner refuses to run it.
    verification = _FINAL_VERIFICATION.read_text()
    formats = _OUTPUT_FORMATS.read_text()

    assert "untrusted input" in verification, (
        "references/final-verification.md no longer treats a queued command as "
        "untrusted, leaving a path from reviewed repository content to a "
        "verbatim Bash execution."
    )
    # Both ends state the rule, each with its own wording: the runner gates
    # before executing, the writer refuses to queue. One end alone is not
    # enforcement - the queue would still carry what the runner declines, or the
    # runner would still execute what the writer let through.
    assert "Check the command before running it" in verification, (
        "references/final-verification.md lost the runner-side command gate, so "
        "step 7 executes whatever the queue holds."
    )
    assert "must be a project verification command" in formats, (
        "output-formats.md lost the writer-side command-shape rule, so anything "
        "a reviewer writes can reach the queue."
    )
    assert "exit refused" in verification, (
        "references/final-verification.md no longer reports a refused command. "
        "A check that was declined must be visible, not silently dropped."
    )


def test_a_command_with_no_verdict_never_records_a_number() -> None:
    # The report line says `exit timeout` but the JSON shape said {"exit": <n>},
    # so the writer had to invent a value - and any number reads as a verdict.
    verification = _FINAL_VERIFICATION.read_text()
    formats = _OUTPUT_FORMATS.read_text()

    assert '`"timeout"`' in formats, (
        "output-formats.md no longer states what result.exit holds for a "
        "timed-out check, so a budget-blown command gets an invented number."
    )
    assert '`"exit": "timeout"`, never a number' in verification, (
        "references/final-verification.md no longer forbids recording a numeric "
        "exit for a command that returned no verdict."
    )


def test_counts_after_a_fix_cycle_are_null_unless_the_suite_re_ran() -> None:
    # The regression loop re-runs only the failing commands, so the full-suite
    # counts belong to a pre-fix HEAD. Recording them against the final sha is
    # exactly the stale reuse the sha gate exists to prevent.
    verification = _FINAL_VERIFICATION.read_text()

    assert "unless the whole suite re-ran clean at the final HEAD" in verification, (
        "references/final-verification.md lost the post-fix-cycle rule. The "
        "review would reuse pre-fix counts against the fixed tree."
    )


def test_the_verification_record_names_its_writer_and_its_reader() -> None:
    verification = _FINAL_VERIFICATION.read_text()

    assert "## Recorded verification result" in verification, (
        "references/final-verification.md has no '## Recorded verification "
        "result' section. Step 7 is the only writer of that file; unwritten, "
        "the review falls back to running the whole suite a second time every "
        "cycle."
    )
    assert _RECORD_PATH in verification, (
        f"references/final-verification.md no longer names {_RECORD_PATH}. "
        "The path is the contract - the reader has no other way to find it."
    )
    for key in ('"sha"', '"cycle"', '"commands"', '"passed"'):
        assert key in verification, (
            f"references/final-verification.md dropped the {key} key from the "
            "record shape. sha gates the reuse, commands says what ran, and the "
            "counts are the Tests: line itself."
        )


def test_unparseable_counts_record_null_rather_than_a_guess() -> None:
    # The dangerous failure is a record that reads green over counts nobody
    # measured. Null is the honest value and sends the reader back to the suite.
    verification = _FINAL_VERIFICATION.read_text()

    assert "no parseable counts records `null` for all three" in verification, (
        "references/final-verification.md lost the null-counts fallback. A "
        "suite whose summary line does not parse must record null, not a "
        "guessed or omitted count."
    )
    assert "empty `commands` array" in verification, (
        "references/final-verification.md lost the empty-commands case: a phase "
        "that ran no suite must write a record the reader treats as absent, "
        "rather than one that reads as a clean run of nothing."
    )
