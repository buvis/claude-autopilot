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
_OUTPUT_FORMATS = (
    _SKILLS / "review-work-completion" / "references" / "output-formats.md"
)

_QUEUE_PATH = "{prd-stem}-checks-{cycle}.json"
_RECORD_PATH = "last-verification.json"


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
    for field in ('"finding"', '"command"', '"source"', '"result"'):
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
