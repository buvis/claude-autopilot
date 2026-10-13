"""Tests for dev/bin/release-checks' count-accumulation helpers (PRD 00256).

Runs the real `run_pytest`/`run_harness`/`run_gather_harness` functions
sourced out of the live script against synthetic commands, so a block's
real reported counts -- not a count of its own `echo "[checks]"` header
lines -- are what the final summary line carries, and a failing block no
longer aborts the whole run.
"""

from __future__ import annotations

import ast
import re
import subprocess
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RELEASE_CHECKS = Path(__file__).resolve().parents[3] / "dev" / "bin" / "release-checks"

UNGATED = (
    "hooks/test_guard_phase_delegation_scratch_replay.py",  # reads gitignored scratch input (docs/dev/tmp/dispatch-*.txt); not reproducible in a clean clone
)


def _tracked_test_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*test_*.py"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def _run_helpers(body: str) -> str:
    """Sources only the helper-function definitions out of the live script
    (everything from `set -uo pipefail` up to the first `echo "[checks]"`
    call), then runs `body` against them. Returns combined stdout+stderr."""
    text = _RELEASE_CHECKS.read_text()
    marker = '\necho "[checks] '
    helpers = text[: text.index(marker)]
    script = f"{helpers}\n{body}\n"
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout + proc.stderr


def test_summary_counts_tests_not_check_blocks() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "3 passed, 1 skipped in 0.01s"; exit 0'
        run_pytest bash -c 'echo "5 passed in 0.02s"; exit 0'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT 0"
        """
    )
    # Real test totals (3+5 passed, 1 skipped), never the two-call count of
    # the script's own echo "[checks]" header lines.
    assert "PASS 8 FAIL 0 SKIP 1 EXIT 0" in out


def test_summary_line_printed_on_failure() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "2 failed, 1 passed in 0.01s"; exit 1'
        EXIT_CODE=0
        if [[ "$TOTAL_FAIL" -ne 0 || "$INFRA_FAIL" -ne 0 ]]; then EXIT_CODE=1; fi
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT $EXIT_CODE"
        """
    )
    assert "PASS 1 FAIL 2 SKIP 0 EXIT 1" in out


def test_infrastructure_failure_is_not_counted_as_a_test_failure() -> None:
    out = _run_helpers(
        """
        run_gather_harness bash -c 'echo "PASS: a"; exit 1'
        EXIT_CODE=0
        if [[ "$TOTAL_FAIL" -ne 0 || "$INFRA_FAIL" -ne 0 ]]; then EXIT_CODE=1; fi
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT $EXIT_CODE"
        """
    )
    # One real PASS: line counted, zero invented failures, but EXIT still
    # non-zero because the harness itself exited non-zero after reporting.
    assert "PASS 1 FAIL 0 SKIP 0 EXIT 1" in out


def test_gather_context_harness_counts_pass_lines() -> None:
    out = _run_helpers(
        """
        run_gather_harness bash -c 'echo "PASS: one"; echo "PASS: two"; exit 0'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT 0"
        """
    )
    assert "PASS 2 FAIL 0 SKIP 0 EXIT 0" in out


_EXIT_LINE = """
    EXIT_CODE=0
    if [[ "$TOTAL_FAIL" -ne 0 || "$INFRA_FAIL" -ne 0 ]]; then EXIT_CODE=1; fi
    echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT $EXIT_CODE"
"""


def test_nonzero_exit_with_zero_failed_count_is_not_reported_green() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "3 passed, 2 errors in 0.1s"; exit 1'
        """
        + _EXIT_LINE
    )
    assert "EXIT 0" not in out
    assert "PASS 3 FAIL 0 SKIP 0 EXIT 1" in out


def test_nonzero_exit_keeps_the_real_failed_count() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "4 failed, 6 passed in 0.1s"; exit 1'
        """
        + _EXIT_LINE
    )
    assert "PASS 6 FAIL 4 SKIP 0 EXIT 1" in out


def test_nonzero_exit_with_a_literal_zero_failed_is_not_reported_green() -> None:
    # "0 failed" parses as the string "0", not as empty: an emptiness check
    # waved this exit 1 through as green (00256 cycle-2 review, R4).
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "3 passed, 0 failed in 0.1s"; exit 1'
        """
        + _EXIT_LINE
    )
    assert "PASS 3 FAIL 0 SKIP 0 EXIT 1" in out


def test_harness_summary_line_supplies_the_measured_totals() -> None:
    out = _run_helpers(
        """
        run_harness bash -c 'echo "ok"; echo "SUMMARY: 7 passed, 0 failed"; exit 0'
        run_harness bash -c 'echo "SUMMARY: 4 passed, 2 failed"; exit 1'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL"
        """
    )
    assert "PASS 11 FAIL 2" in out


def test_harness_without_summary_line_counts_one_pass_per_clean_exit() -> None:
    out = _run_helpers(
        """
        run_harness bash -c 'echo "no summary here"; exit 0'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL"
        """
    )
    assert "PASS 1 FAIL 0" in out


def test_harness_without_summary_line_counts_one_fail_per_bad_exit() -> None:
    out = _run_helpers(
        """
        run_harness bash -c 'echo "no summary here"; exit 3'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL"
        """
    )
    assert "PASS 0 FAIL 1" in out


def test_gate_invokes_the_gate_and_review_verbs_prose_test_sets() -> None:
    text = _RELEASE_CHECKS.read_text()
    assert "skills/run-autopilot/cli/test_gate.py" in text
    assert "skills/review-work-completion/scripts/test_review_verbs_prose.py" in text


# The repo's review-verb test modules, HAND-WRITTEN: the `cli/` files the
# two globs below reach, plus the review-verb modules no glob can reach. Paths
# are repo-relative because the modules span three directories.
_REVIEW_VERB_TEST_FILES = (
    "skills/run-autopilot/cli/test_review_close.py",
    "skills/run-autopilot/cli/test_review_close_apply.py",
    "skills/run-autopilot/cli/test_review_close_carry.py",
    "skills/run-autopilot/cli/test_review_close_lowsev.py",
    "skills/run-autopilot/cli/test_review_close_tail_sweep.py",
    "skills/run-autopilot/cli/test_review_stage.py",
    "skills/run-autopilot/cli/test_review_stage_paths.py",
    "skills/run-autopilot/cli/test_gate.py",
    "skills/run-autopilot/cli/test_gate_findings_table.py",
    "skills/run-autopilot/cli/test_gate_findings_classification.py",
    "skills/run-autopilot/cli/test_gate_findings_shapes.py",
    "skills/run-autopilot/cli/test_gate_findings_unread_shapes.py",
    "skills/run-autopilot/cli/test_gate_findings_real_fixtures.py",
    "skills/run-autopilot/cli/test_verification.py",
    "skills/run-autopilot/cli/test_verification_dirty.py",
    "skills/run-autopilot/cli/test_verification_dirty_symlink.py",
    "skills/run-autopilot/cli/test_verification_hidden_flags.py",
    "skills/run-autopilot/cli/test_verification_dirty_paths.py",
    "skills/run-autopilot/cli/test_verification_log_sink.py",
    "skills/run-autopilot/cli/test_state_no_change.py",
    "skills/run-autopilot/cli/test_cli_review_verbs.py",
    "skills/run-autopilot/cli/test_release_checks_counts.py",
    "skills/run-autopilot/cli/test_main_review_close_validation.py",
    "skills/run-autopilot/cli/test_store_tree_legibility.py",
    "skills/run-autopilot/cli/test_role_effort.py",
    "skills/run-autopilot/scripts/test_phase_review_closes_via_review_close.py",
    "skills/review-work-completion/scripts/test_review_verbs_prose.py",
    "skills/review-work-completion/scripts/test_skill_stages_via_review_stage.py",
    "skills/work/scripts/test_gate_record_writer_prose.py",
)

_GLOB_DIR = "skills/run-autopilot/cli"
_GLOBS = ("test_review*.py", "test_gate*.py")


def _literal_tuple(name: str) -> tuple[str, ...]:
    """The string constants of the module-level tuple `name`, proving it is
    assigned exactly once as a literal tuple of string constants: a tuple
    derived from the glob always equals the glob and so can never fail."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    ]
    assert len(values) == 1, f"{name} must be assigned exactly once"
    assert isinstance(values[0], ast.Tuple) and all(
        isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        for elt in values[0].elts
    ), f"{name} must be a literal tuple of string constants"
    return tuple(elt.value for elt in values[0].elts)


def _in_globs(names: Iterable[str]) -> set[str]:
    """Those of `names` matching one of `_GLOBS`."""
    return {name for name in names if any(fnmatch(name, pat) for pat in _GLOBS)}


def test_every_review_verb_test_file_is_listed() -> None:
    """The review-verb test modules on disk and the ones the gate's `review
    verbs` block runs agree, so a new one cannot be silently left out of the
    gate the way the twelve 00265 found were.
    """
    entries = _literal_tuple("_REVIEW_VERB_TEST_FILES")
    duplicates = sorted({path for path in entries if entries.count(path) > 1})
    assert duplicates == [], (
        f"_REVIEW_VERB_TEST_FILES lists {duplicates} more than once"
    )
    absent = [path for path in entries if not (_ROOT / path).is_file()]
    assert absent == [], (
        f"_REVIEW_VERB_TEST_FILES names {absent}, which is not a file in this "
        "checkout - pytest would fail on the path, or worse, collect nothing"
    )
    text = _RELEASE_CHECKS.read_text()
    unrun = [path for path in entries if path not in text]
    assert unrun == [], f"{_RELEASE_CHECKS}: does not name {unrun}"
    # Discovery agreement: a NEW `cli/` review-verb module fails here loudly
    # instead of never running in the gate.
    on_disk = _in_globs(path.name for path in (_ROOT / _GLOB_DIR).iterdir())
    listed = _in_globs(
        Path(path).name for path in entries if str(Path(path).parent) == _GLOB_DIR
    )
    assert on_disk == listed, (
        f"{_GLOB_DIR}: {sorted(on_disk - listed)} not in _REVIEW_VERB_TEST_FILES; "
        f"_REVIEW_VERB_TEST_FILES: {sorted(listed - on_disk)} not on disk"
    )


def test_release_refuses_while_a_held_prd_blocks_it(tmp_path: Path) -> None:
    """dev/bin/release derives REPO_ROOT purely from $0's own location
    (REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"), so the only fixture
    that works is a real copy of the script at <fixture>/dev/bin/release,
    with a stub claude-plugins sibling at <fixture's parent>/claude-plugins.
    """
    fixture_root = tmp_path / "repo"
    bin_dir = fixture_root / "dev" / "bin"
    bin_dir.mkdir(parents=True)
    release_src = (_ROOT / "dev" / "bin" / "release").read_text(encoding="utf-8")
    release_copy = bin_dir / "release"
    release_copy.write_text(release_src, encoding="utf-8")
    release_copy.chmod(0o755)

    plugins_dir = tmp_path / "claude-plugins" / "scripts"
    plugins_dir.mkdir(parents=True)
    sentinel = tmp_path / "release-plugin-ran"
    stub = plugins_dir / "release-plugin"
    stub.write_text(f"#!/usr/bin/env bash\ntouch {sentinel}\n", encoding="utf-8")
    stub.chmod(0o755)

    for lifecycle_dir, filename in (("hold", "0001-x.md"), ("wip", "0002-y.md")):
        prd_dir = fixture_root / "docs" / "dev" / "project-management" / "prds" / lifecycle_dir
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / filename).write_text(
            "---\n---\n# A PRD\n\nThe next release is blocked on this PRD.\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [str(release_copy)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1, (lifecycle_dir, result.stdout, result.stderr)
        assert not sentinel.exists(), lifecycle_dir
        assert str(prd_dir / filename) in result.stderr, (lifecycle_dir, result.stderr)

        (prd_dir / filename).unlink()


def _dir_is_bare_target(parent: str, text: str) -> bool:
    """True when `parent` appears in `text` as a whole word (not part of a
    longer path or name, before or after), and never for the repo root
    ("." or ""), which would match any dot in the script."""
    if parent in (".", ""):
        return False
    return (
        re.search(r"(?<![\w/.-])" + re.escape(parent) + r"(?![\w/.-])", text)
        is not None
    )


def test_every_tracked_test_file_is_gated() -> None:
    """Every tracked test_*.py must be named in dev/bin/release-checks (by
    its own path or by a whole directory pytest target that collects it),
    or listed in UNGATED with a reason - a release gate that silently
    excludes files is not the full suite (PRD 00278)."""
    text = _RELEASE_CHECKS.read_text()
    missing = [
        path
        for path in _tracked_test_files()
        if path not in text
        and path not in UNGATED
        and not _dir_is_bare_target(str(Path(path).parent), text)
    ]
    assert missing == [], (
        f"{_RELEASE_CHECKS}: does not name {missing} "
        "(add a [checks] block or UNGATED with a reason)"
    )


def test_a_directory_matching_only_part_of_a_longer_token_is_not_a_gated_target() -> (
    None
):
    """A directory counts as a pytest target only when its path stands alone,
    not when it merely prefixes a longer word elsewhere in the script."""
    body = (
        'echo "[checks] skills/foo/scripts-lane"\n'
        "run_pytest python -m pytest -q skills/bar/scripts\n"
    )
    assert not _dir_is_bare_target("skills/foo/scripts", body)
    assert _dir_is_bare_target("skills/bar/scripts", body)


def test_the_repo_root_is_never_a_gated_target() -> None:
    """A repo-root test file has parent ".", which would otherwise match any
    dot in the script and silently pass the gate pin for an ungated file."""
    assert not _dir_is_bare_target(".", 'echo "[checks] x"\nrun_pytest a.b\n')
    assert not _dir_is_bare_target("", 'echo "[checks] x"\n')
