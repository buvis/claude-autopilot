"""Regression fixtures for consolidate_findings.py's numeric fallback.

Split out of test_consolidate_findings.py to keep that file under the
repo's 800-line file cap (rules/coding-style.md "800 max"); the style gate
flagged the cap at 922 lines after these three tests landed there. Reuses
that file's helpers rather than duplicating them.
"""

from __future__ import annotations

from pathlib import Path

import consolidate_findings as cf
from test_consolidate_findings import _finding, _run, _write


def test_review_00070_approvals_stay_apart_from_the_finding(tmp_path: Path) -> None:
    """Real PRD 00070 review output: ALICE's simplification suggestion and
    two of BLAKE's approving remarks all cite the same file (line-number
    suffixes only), but describe three distinct things. None should merge."""
    alice = _write(
        tmp_path,
        "alice.txt",
        [
            "[ALICE] 🟡 Simplification: test_empty_trash_ages_out_old_batches_only is 34 lines. "
            "It uses nested seed and present closures and a shared names dict that mutates across "
            "three seeding rounds. The PRD asked for a plain three-batch case (40, 2 and 0 days, "
            "expecting a return of 1). The extra boundary matrix (45/35/31/29/3 days) is "
            "behavior-preserving extra coverage, but it makes the test harder to read. Consider "
            "splitting the first three-batch case from the boundary sweep into two tests. | "
            "File: skills/purge-devtmp/scripts/test_purge_devtmp.py:126 | Task: 1",
        ],
    )
    blake = _write(
        tmp_path,
        "blake.txt",
        [
            "[BLAKE] ⚪ test_zero_day_retention_never_deletes_what_this_run_just_trashed goes "
            "beyond the spec's acceptance text. It adds a second scenario with a 40-day-old "
            "expired batch and asserts trash-batches-emptied=1. This is harmless and additive, "
            "and it pins that the retention pass still runs under zero days. | "
            "File: skills/purge-devtmp/scripts/test_purge_devtmp.py:107 | Task: 1",
            "[BLAKE] ⚪ test_empty_trash_ages_out_old_batches_only uses a wider matrix than the "
            "spec's 40/2/0-day case: 45, 35, 31, 29 and 3 days, plus several retention values "
            "and a different keep. The spec's core assertions are present (40-day batch gone, "
            "2-day and today's batches kept, return value 1). Fixing now at local noon avoids a "
            "flake near midnight. This is extra coverage, not scope creep. | "
            "File: skills/purge-devtmp/scripts/test_purge_devtmp.py:125 | Task: 1",
        ],
    )
    result = _run(f"ALICE:{alice}", f"BLAKE:{blake}")
    assert result.returncode == 0
    rows = [ln for ln in result.stdout.splitlines() if " | [" in ln]
    assert len(rows) == 3, result.stdout
    for row in rows:
        assert "[1/2]" in row, row


_REVIEW_00088_LINES = {
    "alice.txt": [
        "[ALICE] 🟡 Subparsers-action lookup is duplicated inside the file: _subparser "
        "(skills/use-qwen/scripts/test_runbook_matches_harness.py:28) and "
        "test_runbook_names_every_harness_subcommand "
        "(skills/use-qwen/scripts/test_runbook_matches_harness.py:37) each re-run "
        "next(action for action in parser._actions if action.choices is not None), and the "
        "two flag tests share an identical 5-line body. Simpler, behavior-preserving: add "
        "_subparsers_action() returning that action, call it from _subparser and from the "
        "subcommand test, and factor the flag loop into _long_flags(subparser) that yields "
        "every -- option except --help; each test then reads for flag in "
        "_long_flags(_subparser(\"vet\")): assert flag in section, flag. | "
        "File: skills/use-qwen/scripts/test_runbook_matches_harness.py | Task: 1",
    ],
    "blake.txt": [
        "[BLAKE] 🟡 Flag drift test uses bare substring matching, so two run flags are "
        "masked by longer ones: --shape is a substring of the documented --shapes and "
        "--bound of --gate-bound. Delete --bound SECONDS or --shape {description,tdd} from "
        '§ 7 and the test still passes, defeating the stated goal that the contract "cannot '
        "drift silently\". The PRD prescribed this assertion literally, so it is a spec "
        "defect faithfully implemented; a word-boundary check (rg-style --shape\\b) would "
        "close it | File: skills/use-qwen/scripts/test_runbook_matches_harness.py:50 | Task: 1",
    ],
    "bob.txt": [
        "[BOB] 🟡 Flag assertions use bare substring containment, so prefix-overlapping "
        "flags are never really pinned: --bound is satisfied by the documented --gate-bound "
        "and --shape by --shapes; drop either from § 7 and the drift test still passes | "
        "File: skills/use-qwen/scripts/test_runbook_matches_harness.py | Task: 1",
    ],
}


def test_review_00088_substring_finding_stays_apart_from_the_dedup_finding(
    tmp_path: Path,
) -> None:
    """Real PRD 00088 review output: ALICE's duplication finding is distinct
    from BLAKE's and BOB's shared substring-matching finding, even though all
    three cite the same file. Non-regression pin: this already passes under
    current code."""
    paths = {
        name.split(".")[0]: _write(tmp_path, name, lines)
        for name, lines in _REVIEW_00088_LINES.items()
    }
    result = _run(
        f"ALICE:{paths['alice']}",
        f"BLAKE:{paths['blake']}",
        f"BOB:{paths['bob']}",
    )
    assert result.returncode == 0
    rows = [ln for ln in result.stdout.splitlines() if " | [" in ln]
    assert len(rows) == 2, result.stdout
    assert any("[1/3]" in row for row in rows), result.stdout
    assert any("[2/3]" in row and "BLAKE, BOB" in row for row in rows), result.stdout


def test_numeric_fallback_requires_three_digit_tokens() -> None:
    """The numeric fallback's floor sits at 3-digit tokens: two shared
    2-digit tokens do not count, two shared 3-digit tokens do, and a mixed
    pair of one 3-digit and one 2-digit token does not (only 2+ tokens at or
    above the floor count). Each pair shares no other matching signal:
    Jaccard and overlap both stay under their thresholds."""
    two_digit_a = _finding("retention windows of 40 and 23 days apply here now")
    two_digit_b = _finding("batches older than 40 or 23 days get purged there soon")
    assert (
        cf.jaccard(cf.tokens(two_digit_a.desc), cf.tokens(two_digit_b.desc))
        < cf.MERGE_THRESHOLD
    )
    assert not cf.match(two_digit_a, two_digit_b)

    three_digit_a = _finding("retention windows of 400 and 230 days apply here now")
    three_digit_b = _finding("batches older than 400 or 230 days get purged there soon")
    assert (
        cf.jaccard(cf.tokens(three_digit_a.desc), cf.tokens(three_digit_b.desc))
        < cf.MERGE_THRESHOLD
    )
    assert cf.match(three_digit_a, three_digit_b)

    mixed_a = _finding("retention windows of 400 and 23 days apply here now")
    mixed_b = _finding("batches older than 400 or 23 days get purged there soon")
    assert cf.jaccard(cf.tokens(mixed_a.desc), cf.tokens(mixed_b.desc)) < cf.MERGE_THRESHOLD
    assert not cf.match(mixed_a, mixed_b)
