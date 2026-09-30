#!/usr/bin/env python3
"""Tests for cli/selection.py - the PRD selection decision.

Binds the rule it encodes: lowest sequence, wip before backlog, `hold/`
unreachable. The last one is asserted structurally (on the signature) because
"the function never scans hold/" is a claim about what it CAN do, and a test
that only checks it did not scan hold this time would pass for a function that
grew a `hold` parameter tomorrow.

The last section covers `select_eligible`, the one I/O-owning function here:
its single-argument signature, where it runs the `eligibility:` check, and the
docstring claim that the rest of the module is pure.
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import pytest

from cli import eligibility, selection


class SequenceTests(unittest.TestCase):
    def test_parses_the_five_digit_prefix(self) -> None:
        self.assertEqual(selection.sequence("00089-extract-core-v1.md"), 89)

    def test_leading_zeros_do_not_make_it_octal(self) -> None:
        self.assertEqual(selection.sequence("00010-x.md"), 10)

    def test_unnumbered_name_has_no_sequence(self) -> None:
        self.assertIsNone(selection.sequence("FASTTRACK-PLAN-v5.md"))

    def test_six_digit_prefix_is_not_truncated_to_five(self) -> None:
        # 001189- must not read as 00118, which would silently mis-order it
        # against a real 00118 PRD.
        self.assertIsNone(selection.sequence("001189-x.md"))

    def test_four_digit_prefix_is_not_a_sequence(self) -> None:
        self.assertIsNone(selection.sequence("0089-x.md"))


class SelectableTests(unittest.TestCase):
    def test_orders_by_sequence_not_by_string(self) -> None:
        # String order would put 00100 before 00089.
        names = ["00100-b.md", "00089-a.md", "00095-c.md"]
        self.assertEqual(
            selection.selectable(names),
            ["00089-a.md", "00095-c.md", "00100-b.md"],
        )

    def test_skips_unnumbered_names(self) -> None:
        # docs/dev/project-management/prds/FASTTRACK-PLAN-v5.md is unnumbered precisely so no
        # PRD picker selects it.
        self.assertEqual(
            selection.selectable(["FASTTRACK-PLAN-v5.md", "00089-a.md"]),
            ["00089-a.md"],
        )

    def test_skips_non_markdown(self) -> None:
        self.assertEqual(
            selection.selectable(["00089-a.md.bak", "00090-b.txt", "00089-a.md"]),
            ["00089-a.md"],
        )

    def test_duplicate_sequence_breaks_on_name_deterministically(self) -> None:
        both = ["00089-zebra.md", "00089-alpha.md"]
        self.assertEqual(
            selection.selectable(both),
            ["00089-alpha.md", "00089-zebra.md"],
        )
        self.assertEqual(selection.selectable(both), selection.selectable(both[::-1]))

    def test_empty_listing_selects_nothing(self) -> None:
        self.assertEqual(selection.selectable([]), [])


class SelectTests(unittest.TestCase):
    def test_wip_lowest_sequence_wins(self) -> None:
        prd, source = selection.select(["00095-b.md", "00089-a.md"], [])
        self.assertEqual((prd, source), ("00089-a.md", "wip"))

    def test_wip_beats_a_lower_numbered_backlog_prd(self) -> None:
        # wip wins WHOLE, not per-number: an in-progress PRD finishes before a
        # lower-numbered backlog one starts.
        prd, source = selection.select(["00099-in-progress.md"], ["00001-older.md"])
        self.assertEqual((prd, source), ("00099-in-progress.md", "wip"))

    def test_backlog_used_only_when_wip_is_empty(self) -> None:
        prd, source = selection.select([], ["00095-b.md", "00089-a.md"])
        self.assertEqual((prd, source), ("00089-a.md", "backlog"))

    def test_wip_holding_only_unselectable_names_falls_through(self) -> None:
        prd, source = selection.select(["notes.txt", "README.md"], ["00089-a.md"])
        self.assertEqual((prd, source), ("00089-a.md", "backlog"))

    def test_both_empty_is_drained(self) -> None:
        self.assertEqual(selection.select([], []), (None, "drained"))

    def test_selection_cannot_reach_hold(self) -> None:
        # hold/ is excluded by construction, not by a rule the caller obeys.
        self.assertEqual(
            list(inspect.signature(selection.select).parameters),
            ["wip", "backlog"],
            "select() must take only wip and backlog; a hold parameter would "
            "make the parked/deferred exclusion optional",
        )


# -- select_eligible: the I/O-owning core both verbs call ----------------------
#
# pytest functions rather than TestCase methods: these need `tmp_path`, which
# cannot be injected into a unittest method.


def _backlog_prd(prds_dir: Path, name: str, command: str) -> None:
    (prds_dir / "backlog").mkdir(parents=True, exist_ok=True)
    (prds_dir / "backlog" / name).write_text(
        f'---\neligibility: "{command}"\n---\n\n# PRD\n',
        encoding="utf-8",
    )


def test_select_eligible_takes_the_prds_dir_as_its_only_argument() -> None:
    # One argument means one derivation of the check's working directory. While
    # the caller supplied it, two callers derived it two different ways and the
    # same PRD's check could run from two different directories.
    assert list(inspect.signature(selection.select_eligible).parameters) == ["prds_dir"]


@pytest.mark.parametrize(
    ("marker_at_the_derived_root", "expected"),
    [(True, ("00090-gated-v1.md", "backlog", 0)), (False, (None, "drained", 1))],
    ids=["marker-at-the-derived-root", "marker-in-the-prds-dir"],
)
def test_the_eligibility_check_runs_from_the_directory_the_prds_dir_derives(
    tmp_path: Path,
    marker_at_the_derived_root: bool,
    expected: tuple[str | None, str, int],
) -> None:
    # `prds_dir` alone names that directory: resolve it, then take parents[3]
    # (for `<root>/docs/dev/project-management/prds` that is `<root>`). The
    # check succeeds only where `marker.txt` is, so this measures where it RAN.
    prds_dir = tmp_path / "a" / "b" / "c" / "d" / "prds"
    _backlog_prd(prds_dir, "00090-gated-v1.md", "test -f marker.txt")
    derived_root = prds_dir.resolve().parents[3]
    marker_dir = derived_root if marker_at_the_derived_root else prds_dir
    (marker_dir / "marker.txt").write_text("x", encoding="utf-8")

    prd, source, skips = selection.select_eligible(prds_dir)

    assert (prd, source, len(skips)) == expected


def test_a_relative_prds_dir_derives_an_absolute_check_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `--prds prds` is a legal argument. Deriving the directory by chopping
    # components off the RAW string leaves nothing, and every check then runs
    # from the filesystem root; resolving first is what the contract says.
    deep = tmp_path / "a" / "b" / "c" / "d"
    prds_dir = deep / "prds"
    _backlog_prd(prds_dir, "00090-gated-v1.md", "test -f marker.txt")
    (tmp_path / "a" / "marker.txt").write_text("x", encoding="utf-8")
    monkeypatch.chdir(deep)

    prd, source, skips = selection.select_eligible(Path("prds"))

    assert (prd, source, skips) == ("00090-gated-v1.md", "backlog", [])


def test_the_check_runs_from_the_resolved_root_when_a_parent_is_a_symlink(
    tmp_path: Path,
) -> None:
    # Symlinked-in prds trees are the case a missing `.resolve()` survives: the
    # lexical parent chain names one real directory and the resolved one names
    # another, and only the resolved root holds the marker.
    real = tmp_path / "real" / "p" / "q" / "r"
    _backlog_prd(real / "prds", "00090-gated-v1.md", "test -f marker.txt")
    link_parent = tmp_path / "s" / "t" / "u"
    link_parent.mkdir(parents=True)
    (link_parent / "link").symlink_to(real, target_is_directory=True)
    prds_dir = link_parent / "link" / "prds"
    derived_root = prds_dir.resolve().parents[3]
    assert derived_root != prds_dir.parents[3], "the symlink must change the answer"
    (derived_root / "marker.txt").write_text("x", encoding="utf-8")

    prd, source, skips = selection.select_eligible(prds_dir)

    assert (prd, source, skips) == ("00090-gated-v1.md", "backlog", [])


def test_a_skip_entry_leaves_the_at_stamp_to_the_caller(tmp_path: Path) -> None:
    # The helper prints nothing and stamps nothing: `autopilot select` adds the
    # `at` key itself, so the helper's entry must not already carry one.
    _backlog_prd(tmp_path / "prds", "00090-blocked-v1.md", "exit 3")

    prd, source, skips = selection.select_eligible(tmp_path / "prds")

    assert (prd, source) == (None, "drained")
    assert [set(entry) for entry in skips] == [{"prd", "command", "exit_code", "note"}]
    assert (skips[0]["command"], skips[0]["exit_code"]) == ("exit 3", 3)


@pytest.mark.parametrize(
    "verdict",
    [(-1, "timeout"), (-1, "error: [Errno 20] Not a directory: '/etc/hosts'")],
    ids=["timeout", "unusable-cwd"],
)
def test_a_check_that_never_answered_keeps_its_note_in_the_skip_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verdict: tuple[int, str],
) -> None:
    # `note` is empty for a command that RAN, whatever it exited with, and names
    # the failure mode only when the command never got to answer. Every other
    # case here exits 3 or 4 with an empty note, so a helper that hardcodes
    # `"note": ""` passes them all and silently erases the one value that
    # distinguishes "the check said no" from "the check could not be run".
    # The stub is the seam under test: producing the note is eligibility's job,
    # carrying it through unchanged is select_eligible's.
    _backlog_prd(tmp_path / "prds", "00090-blocked-v1.md", "sleep 99")
    monkeypatch.setattr(eligibility, "evaluate", lambda command, cwd: verdict)

    prd, source, skips = selection.select_eligible(tmp_path / "prds")

    assert (prd, source) == (None, "drained")
    assert (skips[0]["exit_code"], skips[0]["note"]) == verdict


_EXCEPTION_WORDS = ("takes a path", "lists", "I/O", "shells out", "runs")


def test_the_module_docstring_does_not_claim_purity_it_does_not_have() -> None:
    # `select_eligible` lists directories, reads PRDs and shells out through
    # `from cli import eligibility`. Two specific claims are therefore banned
    # rather than the whole word PURE: the module cannot say it never takes a
    # path, and the exception has to be stated AS an exception - named next to
    # what it actually does, not smuggled in as a trailing aside.
    doc = selection.__doc__ or ""
    assert doc.strip(), "the module keeps a docstring"
    assert "never paths" not in doc, f"the module does take a path:\n{doc}"
    paragraphs = [p for p in doc.split("\n\n") if "select_eligible" in p]
    assert any(
        word in paragraph for paragraph in paragraphs for word in _EXCEPTION_WORDS
    ), (
        "some paragraph must name select_eligible beside what it does to the "
        f"filesystem, one of {_EXCEPTION_WORDS}; none does:\n{doc}"
    )


if __name__ == "__main__":
    unittest.main()
