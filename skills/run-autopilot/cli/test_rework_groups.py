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

    def test_not_applicable_wrapping_a_path_is_the_general_key(self) -> None:
        self.assertEqual(rework_groups.file_key("N/A (skills/x/y.py:77)"), "general")
        self.assertEqual(rework_groups.file_key("n/a (a/b.py:3-9)"), "general")

    def test_line_range_and_anchor_citations_share_the_plain_file_key(self) -> None:
        self.assertEqual(rework_groups.file_key("a/b.py (lines 3-4)"), "a/b.py")
        self.assertEqual(rework_groups.file_key("a/b.py#L12"), "a/b.py")
        self.assertEqual(rework_groups.file_key("docs/g.md (lines 1-2)"), "docs/g.md")
        # Stripping repeats until the key stops changing.
        self.assertEqual(rework_groups.file_key("a/b.py#L12:7"), "a/b.py")

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
            set(by_key), {"prose", "src/app.py", "src/cmd.mdx.py", "a.md.bak"}
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
        md = [_f("docs/a.md"), _f("docs/b.md:2")]
        code = [_f("x/a.py:1"), _f("y/b.py")]
        findings = md + code

        with patch.object(rework_groups, "NON_CRITICAL_CAP", 1):
            groups = rework_groups.group(findings)

        self.assertEqual(len(_non_critical(groups)), 1)
        self.assertNotIn("prose", _by_key(groups))
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
    def test_the_00223_cycle_one_set_yields_at_most_four_non_critical_tasks(
        self,
    ) -> None:
        findings = [
            {"severity": sev, "file": file, "text": f"row {i}", "consensus": "[1/4]"}
            for i, (sev, file) in enumerate(REVIEW_00223_CYCLE_1, 1)
        ]

        groups = rework_groups.group(findings)

        self.assertEqual(len(findings), 40)
        self.assertEqual([g for g in groups if g["critical"]], [])
        self.assertGreater(len(groups), 1)  # several groups, not one dump
        self.assertLessEqual(len(groups), rework_groups.NON_CRITICAL_CAP)

        # The prose rule survives on the real data, and the table's own
        # "no file" marker never becomes a task of its own.
        by_key = _by_key(groups)
        self.assertIn("prose", by_key)
        self.assertNotIn("N/A", by_key)
        prose_rows = [f for f in findings if f["file"].split(":")[0].endswith(".md")]
        self.assertEqual(len(prose_rows), 5)
        self.assertEqual(by_key["prose"]["findings"], prose_rows)
        self.assert_every_finding_kept_once(findings, groups)


# ── CLI wrapper: group-rework ────────────────────────────────────────────
# `_run_group_rework` is a thin wrapper over `rework_groups.group()`: read
# --findings, parse it as JSON, call group(), print/exit. Its grouping
# behavior is proved above; these tests only prove the CLI reads, calls, and
# prints/exits correctly.


def test_cli_prints_one_json_array(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(["a.py"], id="element_is_not_a_dict"),
        pytest.param([{"severity": MED, "text": "t"}], id="element_has_no_file"),
        pytest.param([{"file": "a.py", "text": "t"}], id="element_has_no_severity"),
        pytest.param([{"severity": MED, "file": 3}], id="file_is_not_a_string"),
        pytest.param([{"severity": 3, "file": "a.py"}], id="severity_is_not_a_string"),
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


@pytest.mark.parametrize(
    "setup",
    [
        "missing_file",
        "unreadable_file",
        "non_array_json",
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
    elif setup == "non_array_json":
        findings_path = tmp_path / "findings.json"
        findings_path.write_text(json.dumps({"not": "an array"}), encoding="utf-8")
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
