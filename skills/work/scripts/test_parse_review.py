"""Tests for parse_review.py — the per-task reviewer's output contract.

The contract exists so a malformed reply costs one correction retry instead of
passing as an empty review. So the cases that matter are the near-misses: a
reply that looks like a finding to a human and parses to nothing, and a reply
that claims both `NO FINDINGS` and a finding. Prose really is ignored, and that
is pinned too, or the parser would reject every reviewer that says hello first.

The exit codes are checked through the CLI, not the function, because step 5.7
branches on them: 1 spends the correction retry, 2 is a runner failure.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("parse_review.py")
_SPEC = importlib.util.spec_from_file_location("parse_review", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
parse_review = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(parse_review)


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_two_findings_parse_with_uppercase_severities() -> None:
    result = parse_review.parse(
        "medium | a.py:3 | swallowed OSError | re-raise\n"
        "LOW | b.py:9 | duplicated helper | inline it\n",
    )

    assert result["no_findings"] is False
    assert result["closures"] == []
    assert result["findings"] == [
        {
            "severity": "MEDIUM",
            "file": "a.py:3",
            "issue": "swallowed OSError",
            "fix": "re-raise",
        },
        {
            "severity": "LOW",
            "file": "b.py:9",
            "issue": "duplicated helper",
            "fix": "inline it",
        },
    ]


def test_no_findings_marks_an_empty_review() -> None:
    result = parse_review.parse("NO FINDINGS\n")

    assert result == {"no_findings": True, "findings": [], "closures": []}


def test_closure_lines_parse_with_their_verdict() -> None:
    result = parse_review.parse(
        "CLOSURE | resolved | duplicated helper | inlined at a.py:12\n"
        "CLOSURE | unresolved | swallowed OSError | still caught bare at b.py:4\n",
    )

    assert result["closures"] == [
        {
            "verdict": "resolved",
            "finding": "duplicated helper",
            "evidence": "inlined at a.py:12",
        },
        {
            "verdict": "unresolved",
            "finding": "swallowed OSError",
            "evidence": "still caught bare at b.py:4",
        },
    ]
    assert result["findings"] == []


def test_prose_around_the_contract_lines_is_ignored() -> None:
    # A reviewer that narrates is not a reviewer that broke the contract.
    # "Low-hanging" must not read as a LOW line: only the first word counts,
    # and only its trailing punctuation is stripped.
    result = parse_review.parse(
        "Here is my review of the diff:\n"
        "\n"
        "Low-hanging fruit aside, the logic holds.\n"
        "LOW | b.py:9 | duplicated helper | inline it\n",
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "LOW"


@pytest.mark.parametrize(
    "decorated",
    [
        "- MEDIUM | a.py:3 | swallowed OSError | re-raise",
        "* MEDIUM | a.py:3 | swallowed OSError | re-raise",
        "1. MEDIUM | a.py:3 | swallowed OSError | re-raise",
        "> MEDIUM | a.py:3 | swallowed OSError | re-raise",
        "**MEDIUM** | a.py:3 | swallowed OSError | re-raise",
    ],
)
def test_a_finding_dressed_as_markdown_is_still_a_finding(decorated: str) -> None:
    # Reviewers write markdown. Before this was handled a bulleted finding read
    # as prose and vanished — and it vanished SILENTLY, because the plain
    # finding beside it still made the reply valid. That is the exact silent
    # drop this parser exists to prevent, arriving through the front door.
    result = parse_review.parse(
        f"{decorated}\nLOW | b.py:9 | duplicated helper | inline it\n",
    )

    severities = [finding["severity"] for finding in result["findings"]]
    assert severities == ["MEDIUM", "LOW"]
    assert result["findings"][0]["file"] == "a.py:3"


def test_a_closure_dressed_as_markdown_is_still_a_closure() -> None:
    result = parse_review.parse(
        "- CLOSURE | resolved | duplicated helper | inlined at a.py:12\n",
    )

    assert result["closures"] == [
        {
            "verdict": "resolved",
            "finding": "duplicated helper",
            "evidence": "inlined at a.py:12",
        },
    ]


def test_closure_is_recognised_whatever_its_case() -> None:
    # The contract spells it CLOSURE. Matching case-sensitively would send
    # `closure | resolved | ...` down the prose path and drop a verdict the
    # rework cycle needs to close on — the same silent drop as above.
    result = parse_review.parse(
        "closure | Resolved | duplicated helper | inlined at a.py:12\n",
    )

    assert result["closures"] == [
        {
            "verdict": "resolved",
            "finding": "duplicated helper",
            "evidence": "inlined at a.py:12",
        },
    ]


def test_a_severity_line_missing_its_fields_is_rejected_by_name(
    tmp_path: Path,
) -> None:
    # The whole point: this reads as a finding and parses as nothing.
    reply = tmp_path / "reply.txt"
    reply.write_text("MEDIUM: file.py:12 - issue\n", encoding="utf-8")

    result = _run(reply)

    assert result.returncode == 1
    assert "MEDIUM: file.py:12 - issue" in result.stderr


def test_a_closure_with_an_unknown_verdict_is_rejected(tmp_path: Path) -> None:
    reply = tmp_path / "reply.txt"
    reply.write_text("CLOSURE | maybe | a finding | some evidence\n", encoding="utf-8")

    result = _run(reply)

    assert result.returncode == 1
    assert "resolved or unresolved" in result.stderr


def test_a_reply_with_no_contract_line_is_rejected(tmp_path: Path) -> None:
    reply = tmp_path / "reply.txt"
    reply.write_text("The diff looks fine to me.\n", encoding="utf-8")

    result = _run(reply)

    assert result.returncode == 1
    assert "no finding, closure or NO FINDINGS line" in result.stderr


def test_no_findings_alongside_a_finding_is_rejected(tmp_path: Path) -> None:
    reply = tmp_path / "reply.txt"
    reply.write_text(
        "NO FINDINGS\nLOW | b.py:9 | duplicated helper | inline it\n",
        encoding="utf-8",
    )

    result = _run(reply)

    assert result.returncode == 1
    assert "NO FINDINGS reported alongside a finding" in result.stderr


@pytest.mark.parametrize("body", ["", "   \n\n"])
def test_an_empty_reply_is_a_runner_failure_not_a_contract_failure(
    tmp_path: Path,
    body: str,
) -> None:
    reply = tmp_path / "reply.txt"
    reply.write_text(body, encoding="utf-8")

    assert _run(reply).returncode == 2


def test_a_missing_file_is_a_runner_failure(tmp_path: Path) -> None:
    assert _run(tmp_path / "absent.txt").returncode == 2


def test_a_valid_reply_prints_json_on_stdout(tmp_path: Path) -> None:
    reply = tmp_path / "reply.txt"
    reply.write_text("NO FINDINGS\n", encoding="utf-8")

    result = _run(reply)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "no_findings": True,
        "findings": [],
        "closures": [],
    }
