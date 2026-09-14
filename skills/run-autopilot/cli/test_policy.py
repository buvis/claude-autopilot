#!/usr/bin/env python3
"""Tests for cli/policy.py (F5, the loop task ceiling, and the plan-expansion
verdict built on it) and the `autopilot check-plan` subcommand that exposes
the verdict.

Two layers, matching the rest of the suite: the pure functions are exercised
in-process, and the exit-code contract (0 pass or override, 3 stall, 2 unreadable
input) is pinned as a real CLI process exit via subprocess, the way test_cli.py
pins exits 5/9/10.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli import policy

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"

_SRC_TREE = "src/\n└── a.py"

_NESTED_TREE = "\n".join(
    [
        "src/",
        "├── auth/",
        "│   └── login.py",
        "├── billing/",
        "│   └── invoice.py",
        "└── main.py",
    ]
)

_MIXED_DEPTH_TREE = "\n".join(
    [
        "src/",
        "├── auth/",
        "│   └── login.py",
        "└── main.py",
        "lib/",
        "└── x.py",
    ]
)


def _state_with_tasks(count: int) -> dict:
    """A schema-valid state carrying `count` tasks, shaped like test_cli.py's
    _minimal_state."""
    return {
        "prd": "00004-feature-x.md",
        "phase": "build",
        "next_phase": "build",
        "cycle": 1,
        "tasks": [
            {"id": f"t{i}", "name": f"task {i}", "status": "pending"}
            for i in range(count)
        ],
    }


def _state_with_files(prd: str, files_by_task: list) -> dict:
    """A state like _state_with_tasks whose task i carries files_by_task[i]
    as its `files` entry; None leaves the key out."""
    return {
        "prd": prd,
        "phase": "build",
        "next_phase": "build",
        "cycle": 1,
        "tasks": [
            {"id": f"t{i}", "name": f"task {i}", "status": "pending"}
            if files is None
            else {"id": f"t{i}", "name": f"task {i}", "status": "pending", "files": files}
            for i, files in enumerate(files_by_task)
        ],
    }


def _src_state(count: int) -> dict:
    """`count` tasks, task i filing src/f{i}.py (every one under the _SRC_TREE
    leaf, so drift stays empty)."""
    return _state_with_files(
        "00004-feature-x.md", [[f"src/f{i}.py"] for i in range(count)]
    )


def _prd_text(task_lines: int, tree: str | None = None) -> str:
    """Frontmatter-less PRD body with `task_lines` top-level checkbox lines
    and, when `tree` is given, a `### Repository Structure` fenced block."""
    body = "# PRD: feature x\n\n## Tasks\n\n"
    body += "".join(f"- [ ] task line {i}\n" for i in range(task_lines))
    if tree is not None:
        body += "\n### Repository Structure\n\n```\n" + tree + "\n```\n"
    body += "\n## Acceptance Criteria\n\n- the feature works\n"
    return body


def _sections(note: str) -> list[tuple[str, str]]:
    """(heading, body) per `## ` section of a split note, in note order."""
    out = []
    for chunk in note.split("\n## ")[1:]:
        heading, _sep, body = chunk.partition("\n")
        out.append((heading, body))
    return out


def _prd_00167() -> str:
    """The 00167 (sync-manager merge) shape: four task lines, one leaf
    directory holding one file with a `# Maps to:` trailing comment."""
    return _prd_text(
        4,
        "ddb-core/src/sync_manager/\n"
        "└── mod.rs             # Maps to: fold winner + loser into one commit_merge",
    )


def _state_00167() -> dict:
    """21 planned tasks against _prd_00167: one leaf listed, four sibling
    modules the tree never mentions; t1 spans two modules."""
    files = [
        ["ddb-core/src/sync_manager/mod.rs"],
        ["ddb-core/src/sync_manager/mod.rs", "ddb-core/src/parser/mod.rs"],
        ["ddb-core/src/parser/mod.rs"],
        ["ddb-core/src/parser/frontmatter.rs"],
        ["ddb-core/src/parser/body.rs"],
        ["ddb-core/src/parser/tests.rs"],
        ["ddb-core/src/id_minting/mod.rs"],
        ["ddb-core/src/id_minting/clock.rs"],
        ["ddb-core/src/id_minting/collision.rs"],
        ["ddb-core/src/id_minting/format.rs"],
        ["ddb-core/src/id_minting/tests.rs"],
        ["ddb-core/src/types/mod.rs"],
        ["ddb-core/src/types/record.rs"],
        ["ddb-core/src/types/schema.rs"],
        ["ddb-core/src/types/error.rs"],
        ["ddb-core/src/types/tests.rs"],
        ["ddb-core/src/git_ops/mod.rs"],
        ["ddb-core/src/git_ops/merge.rs"],
        ["ddb-core/src/git_ops/commit.rs"],
        ["ddb-core/src/git_ops/lock.rs"],
        ["ddb-core/src/git_ops/tests.rs"],
    ]
    return _state_with_files("00167-sync-manager-merge.md", files)


def _prd_00169() -> str:
    """The 00169 (concurrent writes) shape: ten task lines and nine leaf
    directories, every file line carrying a `# Maps to:` comment."""
    tree = "\n".join(
        [
            "ddb-core/src/indexer/",
            "├── rebuild.rs          # Maps to: rebuild the index from the working tree",
            "├── mod.rs              # Maps to: indexer entry points",
            "ddb-core/src/parser/",
            "└── mod.rs              # Maps to: frontmatter and body parsing",
            "ddb-core/src/git_ops/",
            "└── write_lock.rs       # Maps to: cross-process write lock",
            "ddb-core/src/types/",
            "└── schema.rs           # Maps to: record schema",
            "ddb-core/src/service/",
            "└── mod.rs              # Maps to: service facade",
            "ddb-core/src/app_contract/",
            "└── output.rs           # Maps to: app output contract",
            "ddb-core/src/ffi/",
            "└── records.rs          # Maps to: FFI record surface",
            "ddb-cli/src/commands/",
            "└── maintenance.rs      # Maps to: maintenance subcommand",
            "tests/e2e/",
            "└── concurrent_writes.rs # Maps to: concurrent writer scenarios",
        ]
    )
    return _prd_text(10, tree)


def _state_00169() -> dict:
    """20 planned tasks against _prd_00169: all inside the nine leaves except
    t19, which also files ddb-core/src/traits.rs under a grouping parent."""
    files = [
        ["ddb-core/src/indexer/rebuild.rs"],
        ["ddb-core/src/indexer/mod.rs"],
        ["ddb-core/src/indexer/rebuild.rs", "ddb-core/src/indexer/walk.rs"],
        ["ddb-core/src/parser/mod.rs"],
        ["ddb-core/src/parser/frontmatter.rs"],
        ["ddb-core/src/git_ops/write_lock.rs"],
        ["ddb-core/src/git_ops/write_lock.rs"],
        ["ddb-core/src/types/schema.rs"],
        ["ddb-core/src/types/record.rs"],
        ["ddb-core/src/service/mod.rs"],
        ["ddb-core/src/service/mod.rs"],
        ["ddb-core/src/app_contract/output.rs"],
        ["ddb-core/src/app_contract/output.rs"],
        ["ddb-core/src/ffi/records.rs"],
        ["ddb-core/src/ffi/records.rs"],
        ["ddb-cli/src/commands/maintenance.rs"],
        ["ddb-cli/src/commands/maintenance.rs"],
        ["tests/e2e/concurrent_writes.rs"],
        ["tests/e2e/lock_contention.rs"],
        ["ddb-core/src/traits.rs", "ddb-core/src/service/mod.rs"],
    ]
    return _state_with_files("00169-concurrent-writes.md", files)


def _prd_00185() -> str:
    """The 00185 (lane routing) shape: three task lines, one leaf directory."""
    return _prd_text(
        3,
        "skills/run-autopilot/cli/\n"
        "├── routing.py\n"
        "├── loop.py\n"
        "└── test_routing.py",
    )


def _state_00185() -> dict:
    """5 planned tasks against _prd_00185, all inside the one leaf."""
    files = [
        ["skills/run-autopilot/cli/routing.py"],
        ["skills/run-autopilot/cli/loop.py"],
        ["skills/run-autopilot/cli/test_routing.py"],
        ["skills/run-autopilot/cli/routing.py", "skills/run-autopilot/cli/test_routing.py"],
        ["skills/run-autopilot/cli/lane.py"],
    ]
    return _state_with_files("00185-lane-routing.md", files)


class PlanOverCeilingTests(unittest.TestCase):
    """The pure decision: the count comes from the snapshot, and the
    comparison is strictly greater-than."""

    def test_under_ceiling_is_not_over(self) -> None:
        over, count = policy.plan_over_ceiling(_state_with_tasks(14))
        self.assertFalse(over)
        self.assertEqual(count, 14)

    def test_exactly_at_ceiling_is_not_over(self) -> None:
        over, count = policy.plan_over_ceiling(_state_with_tasks(15))
        self.assertFalse(over, "the ceiling itself is allowed; only above it stalls")
        self.assertEqual(count, 15)

    def test_one_over_ceiling_is_over(self) -> None:
        over, count = policy.plan_over_ceiling(_state_with_tasks(16))
        self.assertTrue(over)
        self.assertEqual(count, 16)

    def test_ceiling_is_fifteen(self) -> None:
        self.assertEqual(policy.LOOP_TASK_CEILING, 15)

    def test_explicit_ceiling_overrides_the_default(self) -> None:
        over, _count = policy.plan_over_ceiling(_state_with_tasks(16), ceiling=20)
        self.assertFalse(over)

    def test_absent_tasks_field_counts_zero(self) -> None:
        over, count = policy.plan_over_ceiling({"prd": "x.md"})
        self.assertFalse(over, "nothing planned yet is not oversized")
        self.assertEqual(count, 0)

    def test_non_list_tasks_counts_zero_instead_of_raising(self) -> None:
        over, count = policy.plan_over_ceiling({"tasks": "not-a-list"})
        self.assertFalse(over)
        self.assertEqual(count, 0)

    def test_does_not_mutate_the_state_it_reads(self) -> None:
        state = _state_with_tasks(3)
        before = json.dumps(state, sort_keys=True)
        policy.plan_over_ceiling(state)
        policy.plan_expansion(state, _prd_00185())
        self.assertEqual(json.dumps(state, sort_keys=True), before)


class PlanExpansionTests(unittest.TestCase):
    """The plan-expansion verdict on ddb-shaped fixtures: three rules in a
    fixed order, drift from the PRD's Repository Structure tree, the
    frontmatter override, and the Markdown split note."""

    _DRIFT_00167 = (
        "ddb-core/src/git_ops",
        "ddb-core/src/id_minting",
        "ddb-core/src/parser",
        "ddb-core/src/types",
    )

    def test_00167_shape_stalls_on_all_three_rules(self) -> None:
        self.assertEqual(
            policy.prd_modules(_prd_00167()),
            (("ddb-core/src/sync_manager",), ("ddb-core/src/sync_manager/mod.rs",)),
        )
        verdict = policy.plan_expansion(_state_00167(), _prd_00167())
        self.assertTrue(verdict.stall)
        self.assertEqual(verdict.reasons, ("task_count", "expansion", "module_drift"))
        self.assertEqual(verdict.planned, 21)
        self.assertEqual(verdict.prd_tasks, 4)
        self.assertEqual(verdict.expansion, 5.25)
        self.assertEqual(verdict.drift, self._DRIFT_00167)
        self.assertEqual(verdict.unfiled, 0)
        self.assertFalse(verdict.override)

    def test_00169_shape_stalls_on_task_count_alone(self) -> None:
        leaf_dirs, _listed = policy.prd_modules(_prd_00169())
        self.assertEqual(
            leaf_dirs,
            (
                "ddb-cli/src/commands",
                "ddb-core/src/app_contract",
                "ddb-core/src/ffi",
                "ddb-core/src/git_ops",
                "ddb-core/src/indexer",
                "ddb-core/src/parser",
                "ddb-core/src/service",
                "ddb-core/src/types",
                "tests/e2e",
            ),
            "implicit ancestors like ddb-core/src are grouping parents, never leaves",
        )
        verdict = policy.plan_expansion(_state_00169(), _prd_00169())
        self.assertTrue(verdict.stall)
        self.assertEqual(verdict.reasons, ("task_count",))
        self.assertEqual(verdict.planned, 20)
        self.assertEqual(verdict.prd_tasks, 10)
        self.assertEqual(verdict.expansion, 2.0)
        self.assertEqual(verdict.drift, ("ddb-core/src",))
        raised = policy.plan_expansion(_state_00169(), _prd_00169(), ceiling=20)
        self.assertEqual(raised.reasons, (), "the ceiling argument is honored")
        self.assertFalse(raised.stall)

    def test_healthy_00185_shape_passes(self) -> None:
        verdict = policy.plan_expansion(_state_00185(), _prd_00185())
        self.assertFalse(verdict.stall)
        self.assertEqual(verdict.reasons, ())
        self.assertEqual(verdict.drift, ())
        self.assertEqual(verdict.planned, 5)
        self.assertEqual(verdict.prd_tasks, 3)
        self.assertAlmostEqual(verdict.expansion, 5 / 3)
        self.assertEqual(verdict.unfiled, 0)
        self.assertFalse(verdict.override)
        lines = verdict.note.splitlines()
        self.assertEqual(lines[0], "# Split note: 00185-lane-routing.md")
        self.assertEqual(lines[1], "planned=5 prd_tasks=3 expansion=1.67 reasons=none")
        self.assertTrue(verdict.note.endswith("\n"))

    def test_expansion_needs_more_than_eight_planned_tasks(self) -> None:
        prd = _prd_text(2, _SRC_TREE)
        eight = policy.plan_expansion(_src_state(8), prd)
        self.assertFalse(eight.stall, "8 planned is not more than EXPANSION_MIN_TASKS")
        self.assertEqual(eight.reasons, ())
        self.assertEqual(eight.expansion, 4.0)
        self.assertEqual(eight.drift, ())
        nine = policy.plan_expansion(_src_state(9), prd)
        self.assertTrue(nine.stall)
        self.assertEqual(nine.reasons, ("expansion",))
        self.assertEqual(nine.expansion, 4.5)
        self.assertEqual(nine.drift, ())
        floor = policy.plan_expansion(_src_state(8), _prd_text(1, _SRC_TREE))
        self.assertEqual(floor.expansion, 8.0)
        self.assertEqual(
            floor.reasons, (), "a ratio alone never fires at or below EXPANSION_MIN_TASKS"
        )
        self.assertFalse(floor.stall)

    def test_ratio_of_exactly_three_passes(self) -> None:
        verdict = policy.plan_expansion(_src_state(15), _prd_text(5, _SRC_TREE))
        self.assertEqual(verdict.expansion, 3.0)
        self.assertEqual(verdict.reasons, ())
        self.assertFalse(verdict.stall)
        above = policy.plan_expansion(_src_state(10), _prd_text(3, _SRC_TREE))
        self.assertAlmostEqual(above.expansion, 10 / 3)
        self.assertEqual(
            above.reasons, ("expansion",), "just above 3.0 fires; the bound is 3.0, not 4.0"
        )
        self.assertTrue(above.stall)

    def test_one_unlisted_module_passes_and_two_stall(self) -> None:
        prd = _prd_text(3, _SRC_TREE)
        one = policy.plan_expansion(
            _state_with_files("x.md", [["src/a.py"], ["lib/x.py"]]), prd
        )
        self.assertEqual(one.drift, ("lib",))
        self.assertEqual(one.reasons, ())
        self.assertFalse(one.stall)
        two = policy.plan_expansion(
            _state_with_files("x.md", [["src/a.py"], ["lib/x.py"], ["other/y.py"]]),
            prd,
        )
        self.assertEqual(two.drift, ("lib", "other"))
        self.assertEqual(two.reasons, ("module_drift",))
        self.assertTrue(two.stall)
        second = policy.plan_expansion(
            _state_with_files("x.md", [["src/a.py", "lib/x.py"]]), prd
        )
        self.assertEqual(
            second.drift, ("lib",), "every file of a task is inspected, not only the first"
        )

    def test_zero_prd_task_lines_skips_the_ratio_rule(self) -> None:
        verdict = policy.plan_expansion(_src_state(12), _prd_text(0, _SRC_TREE))
        self.assertIsNone(verdict.expansion)
        self.assertEqual(verdict.prd_tasks, 0)
        self.assertEqual(verdict.planned, 12)
        self.assertEqual(verdict.reasons, ())
        self.assertFalse(verdict.stall)
        self.assertEqual(
            verdict.note.splitlines()[1],
            "planned=12 prd_tasks=0 expansion=n/a reasons=none",
        )

    def test_prd_task_lines_counts_only_top_level_checkboxes(self) -> None:
        text = (
            "- [ ] open\n"
            "- [x] done\n"
            "* [ ] star bullet\n"
            "  - [ ] indented\n"
            "- [X] capital x\n"
            "-[ ] no space\n"
        )
        self.assertEqual(policy.prd_task_lines(text), 2)
        self.assertEqual(policy.prd_task_lines(""), 0)

    def test_missing_files_key_counts_as_unfiled_not_exempt(self) -> None:
        state = _state_with_files(
            "x.md", [["src/a.py"], None, [], "src/a.py", ["src/b.py"]]
        )
        verdict = policy.plan_expansion(state, _prd_text(5, _SRC_TREE))
        self.assertEqual(verdict.unfiled, 3)
        self.assertEqual(verdict.planned, 5, "unfiled tasks still count as planned")
        self.assertEqual(verdict.drift, ())
        heading, body = _sections(verdict.note)[-1]
        self.assertEqual(heading, "(no files declared)")
        self.assertEqual(
            [line for line in body.splitlines() if line],
            ["- t1 task 1", "- t2 task 2", "- t3 task 3"],
        )

    def test_no_repository_structure_block_skips_drift(self) -> None:
        prd = _prd_text(4)
        self.assertIsNone(policy.prd_modules(prd))
        fence_after_next_heading = (
            prd + "\n### Repository Structure\n\nprose only\n\n## Notes\n\n```\nsrc/\n```\n"
        )
        self.assertIsNone(policy.prd_modules(fence_after_next_heading))
        state = _state_with_files(
            "x.md", [["a/x.py"], ["b/y.py"], ["c/z.py"], ["d/w.py", "e/v.py"]]
        )
        verdict = policy.plan_expansion(state, prd)
        self.assertEqual(verdict.drift, ())
        self.assertEqual(verdict.reasons, ())
        self.assertFalse(verdict.stall)
        self.assertIn(
            "drift: skipped (no Repository Structure)", verdict.note.splitlines()
        )

    def test_only_leaf_directories_grant_recursive_coverage(self) -> None:
        prd = _prd_text(4, _NESTED_TREE)
        self.assertEqual(
            policy.prd_modules(prd),
            (
                ("src/auth", "src/billing"),
                ("src/auth/login.py", "src/billing/invoice.py", "src/main.py"),
            ),
        )
        covered = policy.plan_expansion(
            _state_with_files("x.md", [["src/auth/x.py"], ["src/billing/y.py"]]), prd
        )
        self.assertEqual(covered.drift, ())
        scattered = policy.plan_expansion(
            _state_with_files(
                "x.md",
                [
                    ["src/auth/x.py"],
                    ["src/billing/y.py"],
                    ["src/payments/a.py"],
                    ["src/other/b.py"],
                ],
            ),
            prd,
        )
        self.assertEqual(scattered.drift, ("src/other", "src/payments"))
        self.assertEqual(scattered.reasons, ("module_drift",))
        self.assertTrue(scattered.stall)
        prefix = policy.plan_expansion(
            _state_with_files("x.md", [["src/auth_legacy/x.py"]]), prd
        )
        self.assertEqual(
            prefix.drift,
            ("src/auth_legacy",),
            "a leaf covers only paths past its `/`, never a bare string prefix",
        )

    def test_leaves_at_mixed_depths_all_grant_coverage(self) -> None:
        prd = _prd_text(2, _MIXED_DEPTH_TREE)
        self.assertEqual(
            policy.prd_modules(prd),
            (("lib", "src/auth"), ("lib/x.py", "src/auth/login.py", "src/main.py")),
            "a leaf is any recorded directory without a listed descendant, at any depth",
        )
        verdict = policy.plan_expansion(
            _state_with_files("x.md", [["lib/y.py"], ["src/auth/x.py"]]), prd
        )
        self.assertEqual(verdict.drift, ())
        self.assertEqual(verdict.reasons, ())

    def test_grouping_parent_files_are_individually_allowed(self) -> None:
        prd = _prd_text(2, _NESTED_TREE)
        listed = policy.plan_expansion(_state_with_files("x.md", [["src/main.py"]]), prd)
        self.assertEqual(listed.drift, ())
        sibling = policy.plan_expansion(
            _state_with_files("x.md", [["src/main.py"], ["src/other.py"]]), prd
        )
        self.assertEqual(sibling.drift, ("src",))
        self.assertEqual(sibling.reasons, (), "one drifting module is within MODULE_DRIFT_MAX")
        self.assertFalse(sibling.stall)
        basename = policy.plan_expansion(
            _state_with_files("x.md", [["vendor/main.py"]]), prd
        )
        self.assertEqual(
            basename.drift, ("vendor",), "a listed file matches by full path, not basename"
        )

    def test_root_file_does_not_allow_the_whole_repository(self) -> None:
        prd = _prd_text(2, "README.md")
        self.assertEqual(policy.prd_modules(prd), ((), ("README.md",)))
        verdict = policy.plan_expansion(
            _state_with_files("x.md", [["README.md"], ["foo/bar.py"]]), prd
        )
        self.assertEqual(verdict.drift, ("foo",))
        self.assertNotIn(".", verdict.drift)

    def test_override_frontmatter_skips_every_rule(self) -> None:
        prd = "---\nplan_expansion: allow\n---\n" + _prd_00167()
        verdict = policy.plan_expansion(_state_00167(), prd)
        self.assertTrue(verdict.override)
        self.assertFalse(verdict.stall)
        self.assertEqual(verdict.reasons, ())
        self.assertEqual(verdict.planned, 21)
        self.assertEqual(verdict.prd_tasks, 4)
        self.assertEqual(verdict.drift, self._DRIFT_00167, "drift is still reported")
        for module in self._DRIFT_00167:
            self.assertIn(f"## {module} (UNLISTED)", verdict.note)
        override_lines = [
            line for line in verdict.note.splitlines() if line.startswith("override:")
        ]
        self.assertEqual(len(override_lines), 1)
        self.assertTrue(
            override_lines[0].startswith("override: plan_expansion: allow (rules skipped:")
        )
        for reason in ("task_count", "expansion", "module_drift"):
            self.assertIn(reason, override_lines[0])
        mention = policy.plan_expansion(
            _state_00167(), _prd_00167() + "\nSet `plan_expansion: allow` to opt out.\n"
        )
        self.assertFalse(
            mention.override,
            "a body mention is not an opt-in; only the leading frontmatter block counts",
        )
        self.assertTrue(mention.stall)
        self.assertEqual(mention.reasons, ("task_count", "expansion", "module_drift"))
        self.assertFalse(any(line.startswith("override:") for line in mention.note.splitlines()))

    def test_thresholds_are_pinned(self) -> None:
        self.assertEqual(policy.LOOP_TASK_CEILING, 15)
        self.assertEqual(policy.EXPANSION_RATIO_MAX, 3.0)
        self.assertEqual(policy.EXPANSION_MIN_TASKS, 8)
        self.assertEqual(policy.MODULE_DRIFT_MAX, 1)
        self.assertEqual(policy.PLAN_EXPANSION_OVERRIDE_KEY, "plan_expansion")

    def test_verdict_is_frozen(self) -> None:
        verdict = policy.plan_expansion(_state_00185(), _prd_00185())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            verdict.stall = True

    def test_does_not_mutate_filed_tasks(self) -> None:
        state = _state_00167()
        before = json.dumps(state, sort_keys=True)
        policy.plan_expansion(state, _prd_00167())
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_note_groups_tasks_by_module_and_marks_unlisted(self) -> None:
        note = policy.plan_expansion(_state_00167(), _prd_00167()).note
        lines = note.splitlines()
        self.assertEqual(lines[0], "# Split note: 00167-sync-manager-merge.md")
        self.assertTrue(lines[1].startswith("planned=21 prd_tasks=4 expansion=5.25 reasons="))
        for reason in ("task_count", "expansion", "module_drift"):
            self.assertIn(reason, lines[1])
        self.assertFalse(any(line.startswith("override:") for line in lines))
        self.assertNotIn("drift: skipped", note)
        sections = _sections(note)
        self.assertEqual(
            [heading for heading, _body in sections],
            [
                "ddb-core/src/git_ops (UNLISTED)",
                "ddb-core/src/id_minting (UNLISTED)",
                "ddb-core/src/parser (UNLISTED)",
                "ddb-core/src/types (UNLISTED)",
                "ddb-core/src/sync_manager (listed)",
            ],
            "UNLISTED first, then listed, each group sorted by module; no unfiled section",
        )
        bodies = dict(sections)
        self.assertEqual(
            [line for line in bodies["ddb-core/src/sync_manager (listed)"].splitlines() if line],
            [
                "- t0 task 0: ddb-core/src/sync_manager/mod.rs",
                "- t1 task 1: ddb-core/src/sync_manager/mod.rs",
            ],
        )
        self.assertIn(
            "- t1 task 1: ddb-core/src/parser/mod.rs",
            bodies["ddb-core/src/parser (UNLISTED)"].splitlines(),
            "a task spanning two modules appears under each",
        )
        self.assertTrue(note.endswith("\n"))
        paired = policy.plan_expansion(
            _state_with_files("x.md", [["src/a.py", "src/b.py"]]), _prd_text(1, _SRC_TREE)
        ).note
        self.assertEqual(
            [line for line in dict(_sections(paired))["src (listed)"].splitlines() if line],
            ["- t0 task 0: src/a.py, src/b.py"],
            "one task's files in one module share a line, `, `-joined in task order",
        )


class CheckPlanCliTests(unittest.TestCase):
    """The plan-expansion gate as a real process: exit 0 on pass or override,
    3 on a stall (with the split note on disk and the stall instruction on
    stderr), 2 on a missing state or PRD."""

    _OVERRIDE = "---\nplan_expansion: allow\n---\n"

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_MAIN), *args],
            capture_output=True,
            text=True,
        )

    def _write_state(self, tmp: Path, state: dict) -> Path:
        state_path = tmp / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return state_path

    def _write_prd(
        self, tmp: Path, text: str, name: str = "00004-feature-x.md"
    ) -> Path:
        prd_path = tmp / name
        prd_path.write_text(text, encoding="utf-8")
        return prd_path

    def _stall_lines(self, numbers: str, reasons: str, note_path: Path) -> list[str]:
        """The two stderr lines the stall branch prints, by contract."""
        return [
            f"autopilot: plan expansion gate: {numbers}; note {note_path}",
            'Loop mode: stall this PRD (site "plan_expansion", detail '
            f'"{reasons}; note {note_path}"). '
            "Interactive: this is a warning, continue.",
        ]

    def test_under_ceiling_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(15))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_over_ceiling_exits_three_and_names_both_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("16", result.stderr)
        self.assertIn("15", result.stderr)
        self.assertIn("task_count 16 > 15", result.stderr)
        self.assertIn("plan_expansion", result.stderr)
        self.assertNotIn("oversized_plan", result.stderr)

    def test_ceiling_flag_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--ceiling",
                    "20",
                ],
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_parser_exposes_no_count_flag(self) -> None:
        """The count must never be suppliable by the caller being gated."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--count",
                    "3",
                ],
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--count", result.stderr)

    def test_missing_state_fails_loud_rather_than_passing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "state.json"
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(missing), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("check-plan failed", result.stderr)

    def test_corrupt_state_fails_loud_rather_than_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "state.json"
            corrupt.write_text("not json", encoding="utf-8")
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(corrupt), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("check-plan failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_stall_writes_split_note_and_names_the_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), _prd_00167())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            note = note_path.read_text(encoding="utf-8")
        self.assertIn("UNLISTED", note)
        self.assertEqual(
            note.splitlines()[:2],
            [
                "# Split note: 00167-sync-manager-merge.md",
                "planned=21 prd_tasks=4 expansion=5.25 "
                "reasons=task_count, expansion, module_drift",
            ],
            "the note on disk is the verdict's note, headed by the state's prd",
        )
        headings = [heading for heading, _body in _sections(note)]
        self.assertIn("ddb-core/src/parser (UNLISTED)", headings)
        self.assertIn("ddb-core/src/sync_manager (listed)", headings)
        self.assertIn("plan_expansion", result.stderr)
        self.assertIn("module_drift", result.stderr)
        self.assertIn(str(note_path), result.stderr)
        self.assertEqual(
            result.stderr.splitlines()[:2],
            [
                "autopilot: plan expansion gate: task_count 21 > 15, "
                "expansion 5.25 > 3.0 (planned 21 > 8), "
                "module_drift 4 > 1 (ddb-core/src/git_ops, ddb-core/src/id_minting, "
                f"ddb-core/src/parser, ddb-core/src/types); note {note_path}",
                'Loop mode: stall this PRD (site "plan_expansion", detail '
                f'"task_count, expansion, module_drift; note {note_path}"). '
                "Interactive: this is a warning, continue.",
            ],
        )
        self.assertNotIn("oversized_plan", result.stderr)

    def test_stall_names_only_the_task_count_when_it_alone_fires(self) -> None:
        """00169: 20 tasks over the ceiling, ratio 2.0 and one drifting module
        stay under their bounds, so neither appears in the numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00169())
            prd_path = self._write_prd(Path(tmp), _prd_00169())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            note = note_path.read_text(encoding="utf-8")
        self.assertEqual(
            result.stderr.splitlines()[:2],
            self._stall_lines("task_count 20 > 15", "task_count", note_path),
        )
        self.assertEqual(
            note.splitlines()[1],
            "planned=20 prd_tasks=10 expansion=2.00 reasons=task_count",
        )

    def test_raised_ceiling_leaves_expansion_and_drift_to_stall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), _prd_00167())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--ceiling",
                    "30",
                ],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
        self.assertEqual(
            result.stderr.splitlines()[:2],
            self._stall_lines(
                "expansion 5.25 > 3.0 (planned 21 > 8), "
                "module_drift 4 > 1 (ddb-core/src/git_ops, ddb-core/src/id_minting, "
                "ddb-core/src/parser, ddb-core/src/types)",
                "expansion, module_drift",
                note_path,
            ),
        )
        self.assertNotIn("task_count", result.stderr)

    def test_prd_task_lines_decide_the_expansion_verdict(self) -> None:
        """Ten filed tasks pass against four PRD task lines (2.50) and stall
        against three (3.33): the ratio is read from the PRD, not assumed."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(10))
            prd_path = self._write_prd(Path(tmp), _prd_text(4, _SRC_TREE))
            passed = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(passed.stderr, "")
        self.assertFalse(split_notes_exists, "a ratio of 2.50 writes no split note")
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(10))
            prd_path = self._write_prd(Path(tmp), _prd_text(3, _SRC_TREE))
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            stalled = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(stalled.returncode, 3, stalled.stderr)
            self.assertTrue(note_path.exists(), stalled.stderr)
        self.assertEqual(
            stalled.stderr.splitlines()[:2],
            self._stall_lines(
                "expansion 3.33 > 3.0 (planned 10 > 8)", "expansion", note_path
            ),
        )

    def test_note_is_named_after_the_prd_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(
                Path(tmp), _prd_00167(), name="00167-sync-manager-merge.md"
            )
            note_path = Path(tmp) / "split-notes" / "00167-sync-manager-merge.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            self.assertEqual(
                [p.name for p in (Path(tmp) / "split-notes").iterdir()],
                ["00167-sync-manager-merge.md"],
                "the note carries the --prd stem, never a fixed name",
            )
        first, second = result.stderr.splitlines()[:2]
        self.assertTrue(first.endswith(f"; note {note_path}"), first)
        self.assertIn(f'; note {note_path}")', second)

    def test_override_exits_zero_and_says_why(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), self._OVERRIDE + _prd_00167())
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr.splitlines(),
            [
                "autopilot: check-plan: plan_expansion: allow set in PRD frontmatter; "
                "skipping task_count, expansion, module_drift; "
                "plan-expansion: unfiled=0; drift=checked",
            ],
        )
        self.assertFalse(split_notes_exists, "an override writes no split note")

    def test_body_mention_of_the_override_key_is_not_an_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(
                Path(tmp),
                _prd_00167() + "\nSet `plan_expansion: allow` to opt out.\n",
            )
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
        self.assertIn("module_drift", result.stderr)
        self.assertNotIn(
            "plan_expansion: allow set",
            result.stderr,
            "only the leading frontmatter block opts out, not a body mention",
        )

    def test_missing_prd_flag_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(3))
            result = self._run(["check-plan", "--state", str(state_path)])
        # _ArgumentParser maps every usage error to exit 1; 2 is reserved for
        # state errors (see the exit-code table in __main__.py's docstring).
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("--prd", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unreadable_prd_fails_loud(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(3))
            missing = Path(tmp) / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(missing)],
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(f"check-plan failed: cannot read PRD {missing}", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_success_reports_unfiled_and_skipped_drift(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, ["src/b.py"]],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            result.stderr,
        )
        self.assertFalse(split_notes_exists, "a pass writes no split note")

    def test_fully_filed_plan_with_a_tree_passes_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(3))
            prd_path = self._write_prd(Path(tmp), _prd_text(3, _SRC_TREE))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr,
            "",
            "nothing unfiled and drift checked: no diagnostic at all",
        )
        self.assertFalse(split_notes_exists)

    def test_pass_diagnostic_counts_every_unfiled_task(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, []],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr.splitlines(),
            ["plan-expansion: unfiled=2; drift=skipped (no Repository Structure)"],
            "a missing `files` key and an empty list are both unfiled",
        )
        self.assertFalse(split_notes_exists)

    def test_override_combines_diagnostics_on_one_line(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, ["src/b.py"]],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), self._OVERRIDE + _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertIn("plan_expansion: allow", lines[0])
        self.assertIn(
            "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            lines[0],
        )
        self.assertEqual(
            lines,
            [
                "autopilot: check-plan: plan_expansion: allow set in PRD frontmatter; "
                "skipping task_count, expansion, module_drift; "
                "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            ],
            "the skipped-rules list is a fixed literal; only the diag varies",
        )
        self.assertFalse(split_notes_exists)

    def test_stall_detail_reaches_the_stalled_report(self) -> None:
        """The detail check-plan prints is lifted verbatim into `stall` and
        `render report --stalled`, so the note path lands in the report."""
        state = {
            **_state_00167(),
            "prd": "00004-feature-x.md",
            "batch": {"id": "202609141200", "completed_prds": []},
        }
        with tempfile.TemporaryDirectory() as tmp:
            ap_dir = Path(tmp) / "dev" / "local" / "autopilot"
            prds = Path(tmp) / "dev" / "local" / "prds"
            ap_dir.mkdir(parents=True)
            for sub in ("backlog", "wip", "hold"):
                (prds / sub).mkdir(parents=True)
            state_path = self._write_state(ap_dir, state)
            wip_prd = prds / "wip" / "00004-feature-x.md"
            wip_prd.write_text(_prd_00167(), encoding="utf-8")
            note_path = ap_dir / "split-notes" / "00004-feature-x.md"

            gate = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(wip_prd)],
            )
            self.assertEqual(gate.returncode, 3, gate.stderr)
            details = re.findall(r'detail "([^"]*)"', gate.stderr)
            self.assertEqual(
                details,
                [f"task_count, expansion, module_drift; note {note_path}"],
                gate.stderr,
            )
            detail = details[0]

            stall = self._run(
                [
                    "stall",
                    "--state",
                    str(state_path),
                    "--prd",
                    "00004-feature-x.md",
                    "--site",
                    "plan_expansion",
                    "--detail",
                    detail,
                ],
            )
            self.assertEqual(stall.returncode, 0, stall.stderr)
            self.assertTrue((prds / "hold" / "00004-feature-x.md").exists())
            self.assertFalse(wip_prd.exists())

            report = self._run(
                [
                    "render",
                    "report",
                    "--state",
                    str(state_path),
                    "--stalled",
                    "--site",
                    "plan_expansion",
                    "--detail",
                    detail,
                    "--now",
                    "2026-09-14T12:00:00Z",
                ],
            )
            self.assertEqual(report.returncode, 0, report.stderr)
            text = (ap_dir / "reports" / "202609141200-report.md").read_text(
                encoding="utf-8",
            )
        self.assertIn("STALLED (plan_expansion)", text)
        self.assertIn(str(note_path), text)


if __name__ == "__main__":
    unittest.main()
