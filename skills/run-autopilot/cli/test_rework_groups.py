#!/usr/bin/env python3
"""Tests for cli/rework_groups.py - the rework grouping rule.

`group()` turns the decision gate's findings into task groups: every CRITICAL
finding is its own uncapped group, the rest are keyed by file (line suffix
stripped), markdown findings share one `prose` group, and the non-critical
groups are merged down to NON_CRITICAL_CAP (general first, then the closest
directories). The last fixture is the real 00223 cycle-1 findings table.
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import rework_groups
from cli.__main__ import main

CRIT = "\U0001f534"
HIGH = "\U0001f7e0"
MED = "\U0001f7e1"
LOW = "⚪"

_ids = itertools.count(1)


def _f(file: str, severity: str = MED) -> dict:
    return {
        "severity": severity,
        "file": file,
        "text": f"finding {next(_ids)}",
        "consensus": "[1/4]",
    }


def _non_critical(groups: list[dict]) -> list[dict]:
    return [g for g in groups if not g["critical"]]


def _by_key(groups: list[dict]) -> dict[str, dict]:
    return {g["name_hint"]: g for g in _non_critical(groups)}


def _group_holding(groups: list[dict], finding: dict) -> dict:
    holders = [g for g in groups if finding in g["findings"]]
    assert len(holders) == 1, f"{finding} is in {len(holders)} groups"
    return holders[0]


class GroupTestCase(unittest.TestCase):
    def assert_every_finding_kept_once(
        self,
        findings: list[dict],
        groups: list[dict],
    ) -> None:
        placed = [f for g in groups for f in g["findings"]]
        self.assertEqual(len(placed), len(findings))
        for finding in findings:
            self.assertEqual(placed.count(finding), 1, finding)

    def assert_four_distinct_non_critical_groups(self, groups: list[dict]) -> None:
        """Exactly four groups, four distinct keys - `_by_key` hides a collapse."""
        hints = [g["name_hint"] for g in _non_critical(groups)]
        self.assertEqual(len(hints), 4, hints)
        self.assertEqual(len(set(hints)), 4, hints)


class CriticalTests(GroupTestCase):
    def test_critical_findings_stay_separate_and_uncapped(self) -> None:
        criticals = [_f(f"pkg/m{i}.py:{i}", CRIT) for i in range(5)]
        criticals.append(_f("pkg/m0.py:99", CRIT))  # same file as the first
        others = [_f("a/x.py"), _f("b/y.py"), _f("c/z.py"), _f("general")]
        findings = others[:2] + criticals + others[2:]

        groups = rework_groups.group(findings)

        critical_groups = [g for g in groups if g["critical"]]
        self.assertEqual(len(critical_groups), 6)
        self.assertEqual([g["findings"][0] for g in critical_groups], criticals)
        for crit in criticals:
            held = _group_holding(groups, crit)
            self.assertEqual(held["findings"], [crit])
            self.assertEqual(held["name_hint"], rework_groups.file_key(crit["file"]))
        self.assertEqual(len(_non_critical(groups)), 4)
        self.assertEqual(groups[:6], critical_groups)
        self.assert_every_finding_kept_once(findings, groups)

    def test_a_critical_markdown_finding_keeps_its_own_group(self) -> None:
        """A CRITICAL in a spec or doc is a task, not a line in `prose`."""
        crit_md = _f("docs/a.md:3", CRIT)
        prose = [_f("docs/b.md"), _f("README.md:2")]
        code = _f("x/a.py:1")
        findings = [prose[0], crit_md, code, prose[1]]

        groups = rework_groups.group(findings)

        held = _group_holding(groups, crit_md)
        self.assertTrue(held["critical"])
        self.assertEqual(held["name_hint"], "docs/a.md")
        self.assertEqual(held["findings"], [crit_md])
        self.assertEqual(_by_key(groups)["prose"]["findings"], prose)
        self.assertEqual(_by_key(groups)["x/a.py"]["findings"], [code])
        self.assert_every_finding_kept_once(findings, groups)


class FileKeyTests(GroupTestCase):
    def test_line_suffixes_share_one_file_key(self) -> None:
        self.assertEqual(rework_groups.file_key("a.py:10"), "a.py")
        self.assertEqual(rework_groups.file_key("a.py:20-30"), "a.py")
        self.assertEqual(rework_groups.file_key("a.py"), "a.py")
        self.assertEqual(rework_groups.file_key("src/cli/b.py:7"), "src/cli/b.py")
        self.assertEqual(rework_groups.file_key("general"), "general")
        # Only a trailing line suffix is cut, never another colon.
        self.assertEqual(rework_groups.file_key("a.py:oops"), "a.py:oops")
        self.assertEqual(rework_groups.file_key("C:/x/a.py:3"), "C:/x/a.py")

        findings = [_f("a.py:10"), _f("a.py:20-30"), _f("a.py")]
        groups = rework_groups.group(findings)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["name_hint"], "a.py")
        self.assertFalse(groups[0]["critical"])
        self.assertEqual(groups[0]["findings"], findings)


class FileKeyNormalizationTests(GroupTestCase):
    """`N/A` is the table's own "no file" marker, and citations arrive in
    three shapes; every one of them must land on a real key."""

    def test_bare_not_applicable_is_the_general_key(self) -> None:
        for raw in ("N/A", "n/a", "N/a"):
            with self.subTest(raw):
                self.assertEqual(rework_groups.file_key(raw), "general")

    def test_a_path_that_merely_contains_the_marker_keeps_its_own_key(self) -> None:
        # Only the bare marker maps to `general`; these are real files.
        self.assertEqual(rework_groups.file_key("src/gen/a.py"), "src/gen/a.py")
        self.assertEqual(rework_groups.file_key("n/apply.py:3"), "n/apply.py")

    def test_not_applicable_wrapping_a_path_is_the_general_key(self) -> None:
        self.assertEqual(rework_groups.file_key("N/A (skills/x/y.py:77)"), "general")
        self.assertEqual(rework_groups.file_key("n/a (a/b.py:3-9)"), "general")

    def test_line_range_and_anchor_citations_share_the_plain_file_key(self) -> None:
        self.assertEqual(rework_groups.file_key("a/b.py (lines 3-4)"), "a/b.py")
        self.assertEqual(rework_groups.file_key("a/b.py#L12"), "a/b.py")
        # Any anchor line, not only the one the finding happened to name.
        self.assertEqual(rework_groups.file_key("a/b.py#L7"), "a/b.py")
        self.assertEqual(rework_groups.file_key("a/b.py#L1234"), "a/b.py")
        self.assertEqual(rework_groups.file_key("docs/g.md (lines 1-2)"), "docs/g.md")
        self.assertEqual(rework_groups.file_key("docs/g.md (lines 9-120)"), "docs/g.md")
        # A space inside a path is not a separator: only the suffix is cut.
        self.assertEqual(rework_groups.file_key("my docs/a.py:3"), "my docs/a.py")
        self.assertEqual(
            rework_groups.file_key("my docs/a.py (lines 3-4)"),
            "my docs/a.py",
        )
        # Stripping repeats until the key stops changing.
        self.assertEqual(rework_groups.file_key("a/b.py#L12:7"), "a/b.py")

    def test_file_key_strips_singular_line_citation(self) -> None:
        self.assertEqual(rework_groups.file_key("a/b.py (line 3)"), "a/b.py")

    def test_file_key_strips_comma_line_list(self) -> None:
        self.assertEqual(
            rework_groups.file_key("a/b.py (lines 18-22, 423)"), "a/b.py"
        )

    def test_file_key_strips_anchor_range(self) -> None:
        self.assertEqual(rework_groups.file_key("a/b.py#L12-L20"), "a/b.py")

    def test_widened_stripping_leaves_the_colon_suffix_rule_intact(self) -> None:
        self.assertEqual(rework_groups.file_key("a.py:10"), "a.py")
        self.assertEqual(rework_groups.file_key("a.py:20-30"), "a.py")
        self.assertEqual(rework_groups.file_key("a.py"), "a.py")
        self.assertEqual(rework_groups.file_key("general"), "general")
        # A non-numeric suffix is still part of the key.
        self.assertEqual(rework_groups.file_key("a.py:oops"), "a.py:oops")

    def test_every_citation_shape_of_one_file_lands_in_one_group(self) -> None:
        findings = [_f("a/b.py:10"), _f("a/b.py (lines 3-4)"), _f("a/b.py#L12")]

        groups = rework_groups.group(findings)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["name_hint"], "a/b.py")
        self.assertFalse(groups[0]["critical"])
        self.assertEqual(groups[0]["findings"], findings)

    def test_not_applicable_merges_with_general_into_the_smallest_file(self) -> None:
        na, gen, prose = _f("N/A"), _f("general"), _f("docs/notes.md")
        small = [_f("b/y.py:1"), _f("b/y.py:2")]
        findings = [na, gen, prose] + small
        findings += [_f(f"a/x.py:{n}") for n in range(3)]
        findings += [_f(f"c/z.py:{n}") for n in range(4)]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        # The two markers are one group and it merges into the smallest code
        # group. No junk `N/A` key, and no `mixed` group either: a mixed
        # merge here would mean the general rule never fired.
        for absent in ("N/A", "general", "mixed"):
            self.assertNotIn(absent, by_key)
        for present in ("prose", "a/x.py", "c/z.py"):
            self.assertIn(present, by_key)
        merged = _group_holding(groups, na)
        self.assertIs(merged, _group_holding(groups, gen))
        self.assertIs(merged, _group_holding(groups, small[0]))
        self.assertEqual(len(merged["findings"]), 4)
        self.assertEqual(by_key["prose"]["findings"], [prose])
        self.assert_four_distinct_non_critical_groups(groups)
        self.assert_every_finding_kept_once(findings, groups)


class ProseTests(GroupTestCase):
    def test_markdown_findings_share_one_prose_group(self) -> None:
        md = [_f("docs/guide.md:3"), _f("README.md"), _f("skills/x/SKILL.md:1-4")]
        code = _f("src/app.py:5")
        mdx, bak = _f("src/cmd.mdx.py:2"), _f("a.md.bak")  # ".md" not at the end
        findings = [md[0], code, md[1], mdx, md[2], bak]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        self.assertEqual(
            set(by_key),
            {"prose", "src/app.py", "src/cmd.mdx.py", "a.md.bak"},
        )
        self.assertEqual(by_key["prose"]["findings"], md)
        self.assertEqual(by_key["src/app.py"]["findings"], [code])
        self.assertEqual(by_key["src/cmd.mdx.py"]["findings"], [mdx])
        self.assertEqual(by_key["a.md.bak"]["findings"], [bak])


class CapTests(GroupTestCase):
    def test_four_or_fewer_groups_pass_through_unmerged(self) -> None:
        self.assertEqual(rework_groups.NON_CRITICAL_CAP, 4)
        findings = [
            _f("general"),
            _f("docs/a.md"),
            _f("x/a.py:1"),
            _f("x/b.py:2"),
            _f("x/a.py:9"),
        ]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        self.assertEqual(set(by_key), {"general", "prose", "x/a.py", "x/b.py"})
        self.assertEqual(by_key["x/a.py"]["findings"], [findings[2], findings[4]])
        self.assertEqual(by_key["general"]["findings"], [findings[0]])
        self.assert_every_finding_kept_once(findings, groups)
        self.assertEqual(rework_groups.group([]), [])

    def test_grouping_leaves_the_input_findings_unchanged(self) -> None:
        findings = [_f("q.py:4", CRIT), _f("general"), _f("docs/a.md:2")]
        findings += [_f(f"p{i}/m.py:{i}-{i + 1}") for i in range(5)]
        before = copy.deepcopy(findings)

        rework_groups.group(findings)

        self.assertEqual(findings, before)
        self.assertEqual(findings[3]["file"], "p0/m.py:0-1")

    def test_general_merges_into_the_smallest_group_first(self) -> None:
        cases = {
            "strictly smallest": ({"a/x.py": 3, "b/y.py": 2, "c/z.py": 4}, "b/y.py"),
            "tie goes to the lexically first key": (
                {"c/z.py": 2, "a/x.py": 2, "b/y.py": 4},
                "a/x.py",
            ),
        }
        for label, (sizes, target) in cases.items():
            with self.subTest(label):
                findings = [_f("general"), _f("docs/notes.md")]  # prose is smaller
                for path, size in sizes.items():
                    findings += [_f(f"{path}:{n}") for n in range(size)]

                groups = rework_groups.group(findings)

                self.assertEqual(len(_non_critical(groups)), 4)
                self.assertNotIn("general", _by_key(groups))
                merged = _group_holding(groups, findings[0])
                target_finding = next(
                    f for f in findings if f["file"].startswith(target)
                )
                self.assertIs(merged, _group_holding(groups, target_finding))
                self.assertEqual(len(merged["findings"]), sizes[target] + 1)
                prose = _by_key(groups)["prose"]
                self.assertEqual(prose["findings"], [findings[1]])
                self.assert_every_finding_kept_once(findings, groups)

    def test_closest_directories_merge_until_four_remain(self) -> None:
        a, b, c = _f("p/q/r/a.py:1"), _f("p/q/r/b.py"), _f("p/q/s/c.py:2-3")
        d, e, top = _f("p/t/d.py"), _f("x/e.py"), _f("y.py")
        findings = [a, b, c, d, e, top]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        self.assertEqual(set(by_key), {"p/q/", "p/t/d.py", "x/e.py", "y.py"})
        self.assertCountEqual(by_key["p/q/"]["findings"], [a, b, c])
        self.assert_four_distinct_non_critical_groups(groups)
        self.assert_every_finding_kept_once(findings, groups)

    def test_equal_prefixes_merge_the_smallest_pair(self) -> None:
        big = [_f("m/a.py:1"), _f("m/a.py:2"), _f("m/a.py:3")]
        small = [_f("m/b.py"), _f("m/c.py")]
        findings = big + small + [_f("n/x.py"), _f("o/y.py")]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        self.assertEqual(set(by_key), {"m/a.py", "m/", "n/x.py", "o/y.py"})
        self.assertEqual(by_key["m/a.py"]["findings"], big)
        self.assertCountEqual(by_key["m/"]["findings"], small)
        self.assert_four_distinct_non_critical_groups(groups)

    def test_groups_sharing_no_directory_merge_as_mixed(self) -> None:
        findings = []
        for size, path in enumerate(["a.py", "b.py", "c.py", "d.py", "e.py"], 1):
            findings += [_f(path) for _ in range(size)]

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        self.assertEqual(set(by_key), {"mixed", "c.py", "d.py", "e.py"})
        self.assertEqual(len(by_key["mixed"]["findings"]), 3)
        self.assert_four_distinct_non_critical_groups(groups)
        self.assert_every_finding_kept_once(findings, groups)


class ProseFoldTests(GroupTestCase):
    """The `prose` fold is unreachable at NON_CRITICAL_CAP = 4; patching the
    cap down to 1 is the only way to drive it."""

    def test_prose_folds_into_the_last_code_group_under_a_cap_of_one(self) -> None:
        # One code group, so "the last remaining code group" is a named file:
        # the surviving task must still point at it.
        code = _f("y/b.py")
        md = [_f("docs/a.md"), _f("docs/b.md:2")]
        findings = [code] + md

        with patch.object(rework_groups, "NON_CRITICAL_CAP", 1):
            groups = rework_groups.group(findings)

        self.assertEqual(len(_non_critical(groups)), 1)
        self.assertNotIn("prose", _by_key(groups))
        self.assertEqual(_by_key(groups)["y/b.py"]["findings"], findings)
        self.assert_every_finding_kept_once(findings, groups)

    def test_two_code_groups_and_prose_under_a_cap_of_one_keep_every_finding(
        self,
    ) -> None:
        code = [_f("x/a.py:1"), _f("y/b.py")]
        md = [_f("docs/a.md"), _f("docs/b.md:2")]
        findings = code + md

        with patch.object(rework_groups, "NON_CRITICAL_CAP", 1):
            groups = rework_groups.group(findings)

        self.assertEqual(len(_non_critical(groups)), 1)
        self.assertNotIn("prose", _by_key(groups))
        self.assertEqual(_non_critical(groups)[0]["findings"], findings)
        self.assert_every_finding_kept_once(findings, groups)

    def test_prose_only_findings_under_a_cap_of_one_keep_every_finding(self) -> None:
        findings = [_f("docs/a.md"), _f("README.md:3"), _f("skills/x/SKILL.md")]

        with patch.object(rework_groups, "NON_CRITICAL_CAP", 1):
            groups = rework_groups.group(findings)

        self.assertEqual(len(_non_critical(groups)), 1)
        self.assertEqual(_by_key(groups)["prose"]["findings"], findings)
        self.assert_every_finding_kept_once(findings, groups)


class OrderTests(GroupTestCase):
    def test_order_is_critical_then_severity_then_size(self) -> None:
        findings = [
            _f("z.py", LOW),
            _f("z.py", LOW),
            _f("z.py", LOW),
            _f("z.py", LOW),
            _f("b.py", LOW),
            _f("b.py", MED),
            _f("c.py", MED),
            _f("c.py", LOW),
            _f("c.py", MED),
            _f("y.py", HIGH),
            _f("q.py", CRIT),
        ]

        groups = rework_groups.group(findings)

        self.assertTrue(groups[0]["critical"])
        self.assertEqual(groups[0]["findings"], [findings[-1]])
        self.assertEqual(
            [g["name_hint"] for g in groups[1:]],
            ["y.py", "c.py", "b.py", "z.py"],
        )

    def test_the_worst_severity_in_a_group_decides_its_order(self) -> None:
        """A group's rank is its worst finding, not its average: the 🟠 must
        be worked before three 🟡, at equal size."""
        worst_is_high = [_f("z.py", HIGH), _f("z.py", LOW), _f("z.py", LOW)]
        all_medium = [_f("a.py", MED), _f("a.py", MED), _f("a.py", MED)]
        findings = all_medium + worst_is_high

        groups = rework_groups.group(findings)

        # Equal size, and both the key order and the average severity would
        # put `a.py` first.
        self.assertEqual([g["name_hint"] for g in groups], ["z.py", "a.py"])
        self.assertEqual(_by_key(groups)["z.py"]["findings"], worst_is_high)
        self.assertEqual(_by_key(groups)["a.py"]["findings"], all_medium)

    def test_equal_severity_and_size_order_by_key(self) -> None:
        findings = [_f("b.py"), _f("b.py"), _f("a.py"), _f("a.py")]

        groups = rework_groups.group(findings)

        self.assertEqual([g["name_hint"] for g in groups], ["a.py", "b.py"])


# The consolidated findings table of
# docs/dev/project-management/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-review-1.md
# (cycle 1), transcribed as (severity, file) per row, in table order. The table
# holds 40 rows although its heading says "35 findings"; every row is kept.
REVIEW_00223_CYCLE_1 = [
    (HIGH, "skills/run-autopilot/cli/enter.py:211"),
    (HIGH, "skills/run-autopilot/references/phase-build.md:20"),
    (MED, "dev/bin/release-checks:138"),
    (HIGH, "skills/run-autopilot/cli/enter.py:242"),
    (MED, "skills/run-autopilot/cli/selection.py:11"),
    (HIGH, "skills/run-autopilot/cli/__main__.py:594"),
    (HIGH, "skills/run-autopilot/references/phase-build.md:34"),
    (HIGH, "skills/run-autopilot/cli/enter.py:184"),
    (MED, "skills/run-autopilot/references/phase-build.md:42"),
    (MED, "skills/run-autopilot/cli/enter.py:253"),
    (MED, "skills/run-autopilot/cli/test_enter_prose.py:112"),
    (MED, "skills/run-autopilot/cli/enter.py:30"),
    (MED, "skills/run-autopilot/cli/enter.py:246"),
    (MED, "skills/run-autopilot/cli/enter.py:139"),
    (MED, "skills/run-autopilot/cli/enter.py:199"),
    (MED, "skills/run-autopilot/cli/__main__.py:297"),
    (MED, "skills/run-autopilot/cli/enter.py:299"),
    (MED, "skills/run-autopilot/cli/enter.py:329"),
    (MED, "skills/run-autopilot/cli/frontmatter.py:165"),
    (MED, "skills/run-autopilot/cli/selection.py:82"),
    (MED, "skills/run-autopilot/cli/test_enter.py:700"),
    (MED, "skills/run-autopilot/cli/test_enter_prose.py:119"),
    (MED, "skills/run-autopilot/cli/enter.py:159"),
    (MED, "skills/run-autopilot/cli/test_enter_prose.py:115"),
    (MED, "skills/run-autopilot/cli/enter.py:150"),
    (MED, "skills/run-autopilot/cli/enter.py:293"),
    (MED, "skills/run-autopilot/cli/enter.py:289"),
    (LOW, "skills/run-autopilot/cli/enter.py:139"),
    (LOW, "skills/run-autopilot/cli/test_enter_prose.py:112"),
    (LOW, "skills/run-autopilot/cli/__main__.py:293"),
    (LOW, "skills/run-autopilot/cli/enter.py:147"),
    (LOW, "skills/run-autopilot/cli/enter.py:55"),
    (LOW, "skills/run-autopilot/cli/enter.py:293"),
    (LOW, "skills/run-autopilot/cli/enter.py:91"),
    (LOW, "skills/run-autopilot/cli/enter.py:186"),
    (LOW, "skills/run-autopilot/cli/test_enter_prose.py:119"),
    (LOW, "skills/run-autopilot/references/phase-build.md:14"),
    (LOW, "skills/run-autopilot/references/phase-build.md:164"),
    (LOW, "skills/run-autopilot/cli/enter.py:96"),
    (LOW, "N/A"),
]


class Review00223FixtureTests(GroupTestCase):
    @staticmethod
    def _rows() -> list[dict]:
        return [
            {"severity": sev, "file": file, "text": f"row {i}", "consensus": "[1/4]"}
            for i, (sev, file) in enumerate(REVIEW_00223_CYCLE_1, 1)
        ]

    def test_the_00223_cycle_one_set_yields_four_non_critical_tasks(self) -> None:
        findings = self._rows()

        groups = rework_groups.group(findings)

        self.assertEqual(len(findings), 40)
        self.assertEqual([g for g in groups if g["critical"]], [])
        self.assertEqual(len(groups), rework_groups.NON_CRITICAL_CAP)

        # Four real tasks, four distinct keys, no junk `N/A` key: the five
        # `phase-build.md` rows are the prose task, the `N/A` row rides with
        # the single `dev/bin` row (the smallest code task), and the `cli/`
        # rows split in two rather than landing in one 35-row dump.
        by_key = _by_key(groups)
        self.assertEqual(len(by_key), 4)
        self.assertNotIn("N/A", by_key)
        self.assertEqual(
            sorted(len(g["findings"]) for g in _non_critical(groups)),
            [2, 5, 12, 21],
        )
        prose_rows = [f for f in findings if f["file"].split(":")[0].endswith(".md")]
        self.assertEqual(len(prose_rows), 5)
        self.assertEqual(by_key["prose"]["findings"], prose_rows)
        sweep = _group_holding(groups, findings[-1])  # the `N/A` row
        self.assertEqual(
            [f["file"] for f in sweep["findings"]],
            ["dev/bin/release-checks:138", "N/A"],
        )
        self.assert_every_finding_kept_once(findings, groups)

    def test_every_00223_code_task_names_one_file_or_one_directory(self) -> None:
        """The 21 `enter.py` rows are their own task and the rest of `cli/`
        is one directory task: no task mixes unrelated trees."""
        findings = self._rows()

        groups = rework_groups.group(findings)

        by_key = _by_key(groups)
        enter = "skills/run-autopilot/cli/enter.py"
        enter_rows = [f for f in findings if f["file"].startswith(enter)]
        self.assertEqual(len(enter_rows), 21)
        self.assertEqual(by_key[enter]["findings"], enter_rows)

        rest = by_key["skills/run-autopilot/cli/"]["findings"]
        self.assertEqual(len(rest), 12)
        for finding in rest:
            self.assertTrue(
                finding["file"].startswith("skills/run-autopilot/cli/"),
                f"{finding['file']} does not belong to the cli/ task",
            )


# ── CLI wrapper: group-rework ────────────────────────────────────────────
# `_run_group_rework` is a thin wrapper over `rework_groups.group()`: read
# --findings, parse it as JSON, call group(), print/exit. Its grouping
# behavior is proved above; these tests only prove the CLI reads, calls, and
# prints/exits correctly.


def test_cli_prints_one_json_array(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    crit = {"severity": CRIT, "file": "a.py:1", "text": "boom", "consensus": "[4/4]"}
    gen = {"severity": MED, "file": "general", "text": "sweep", "consensus": "[2/4]"}
    code = {"severity": MED, "file": "b/c.py:3", "text": "typo", "consensus": "[1/4]"}
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps([crit, gen, code]), encoding="utf-8")

    exit_code = main(["group-rework", "--findings", str(findings_path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    # Critical first, then the two MED singletons by key: `b/c.py` < `general`.
    assert json.loads(out) == [
        {"name_hint": "a.py", "critical": True, "findings": [crit]},
        {"name_hint": "b/c.py", "critical": False, "findings": [code]},
        {"name_hint": "general", "critical": False, "findings": [gen]},
    ]


def test_cli_output_keeps_non_ascii_literal(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Phase 6 copies this output verbatim into a findings block, so an
    # escaped emoji or dash would have to be decoded by hand.
    finding = _f("a.py:1", HIGH)
    finding["text"] = "widen the fence – not the gate"
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps([finding]), encoding="utf-8")

    exit_code = main(["group-rework", "--findings", str(findings_path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert HIGH in out
    assert "widen the fence – not the gate" in out
    assert "\\u" not in out


def test_cli_groups_a_valid_finding_that_carries_no_consensus(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Only `severity` and `file` are required; every other key rides along.
    finding = {"severity": MED, "file": "a.py:4", "text": "t"}
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps([finding]), encoding="utf-8")

    exit_code = main(["group-rework", "--findings", str(findings_path)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == [
        {"name_hint": "a.py", "critical": False, "findings": [finding]},
    ]


def test_cli_without_the_findings_flag_exits_on_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No implicit default path: the orchestrator must name the file.
    with pytest.raises(SystemExit):
        main(["group-rework"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--findings" in captured.err


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(["a.py"], id="element_is_not_a_dict"),
        pytest.param([{"severity": MED, "text": "t"}], id="element_has_no_file"),
        pytest.param([{"file": "a.py", "text": "t"}], id="element_has_no_severity"),
        pytest.param([{"severity": MED, "file": 3}], id="file_is_not_a_string"),
        pytest.param([{"severity": 3, "file": "a.py"}], id="severity_is_not_a_string"),
        # Every element is checked, not just the first.
        pytest.param(
            [{"severity": MED, "file": "a.py", "text": "t"}, "junk"],
            id="second_element_is_not_a_dict",
        ),
        pytest.param(
            [{"severity": MED, "file": "a.py"}, {"severity": MED, "file": None}],
            id="second_element_has_a_null_file",
        ),
        # A finding can carry `consensus` and still be malformed: the types of
        # `severity` and `file` are what decide.
        pytest.param(
            [{"severity": 3, "file": "a.py", "consensus": "[1/4]"}],
            id="malformed_element_carrying_consensus",
        ),
    ],
)
def test_cli_malformed_element_exits_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    payload: list,
) -> None:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["group-rework", "--findings", str(findings_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1


# JSON bodies that parse but are not an array of findings.
NOT_AN_ARRAY = {
    "object_json": '{"not": "an array"}',
    "number_json": "3",
    "null_json": "null",
    "string_json": '"x"',
}


@pytest.mark.parametrize(
    "setup",
    [
        "missing_file",
        "unreadable_file",
        *NOT_AN_ARRAY,
        "invalid_json",
        "non_utf8_bytes",
    ],
)
def test_cli_malformed_input_exits_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    setup: str,
) -> None:
    if setup == "missing_file":
        findings_path = tmp_path / "does-not-exist.json"
    elif setup == "unreadable_file":
        findings_path = tmp_path  # a directory cannot be read as a file
    elif setup in NOT_AN_ARRAY:
        findings_path = tmp_path / "findings.json"
        findings_path.write_text(NOT_AN_ARRAY[setup], encoding="utf-8")
    elif setup == "invalid_json":
        findings_path = tmp_path / "findings.json"
        findings_path.write_text('[{"severity": ', encoding="utf-8")
    else:
        findings_path = tmp_path / "findings.json"
        findings_path.write_bytes(b"\xff\xfe[]")  # not decodable as UTF-8

    exit_code = main(["group-rework", "--findings", str(findings_path)])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
