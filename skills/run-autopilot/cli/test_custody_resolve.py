#!/usr/bin/env python3
"""Tests for the attended custody surface: `custody.resolve` behind the
`custody resolve` verb and the read-only `custody list` verb of
cli/__main__.py.

Written from the design contract only. Every test drives the CLI as a real
subprocess against a REAL repository (git init plus real commits) whose
custody was seeded the way a cap_critical stall leaves it: marker file,
`recorded` journal row, git-config locator and the state.json mirror. The
custody core (record_critical, refresh_hold_prd, ...) is covered in
test_custody.py; both share custody_testutil.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody
from cli.custody_testutil import (
    _GIT_ENV,
    BATCH_ID,
    _git,
    _init_bare_repo,
    _init_repo,
    _locator,
)

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"
PRD = "00004-feature-x.md"
STEM = "00004-feature-x"
OP_ID = "a1b2c3d4e5f6"
RESOLVE_ID = f"{OP_ID}-resolve"
CUSTODY_BRANCH = f"refs/heads/custody/{STEM}"
# A second, unrelated custody that must survive resolving PRD untouched.
OTHER_PRD = "00005-feature-y.md"
OTHER_OP_ID = "0f1e2d3c4b5a"
# The line `git revert --no-edit` writes; reconciliation is keyed on it.
_REVERTS_RE = re.compile(r"^This reverts commit ([0-9a-f]{40})\.$", re.MULTILINE)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=_GIT_ENV,
        timeout=120,
    )


def _json_lines(text: str) -> list:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class _Custody:
    """One seeded custody: a real repo at <root>/repo (bare-backed by
    <root>/repo.git when `bare`), and under <root>/autopilot the marker, the
    `recorded` journal row, the git-config locator and state.json with the
    entry mirrored under batch.critical_on_master. The range is c0..c2
    (targets c1, c2), or EMPTY_TREE..c2 (all three) with `empty_tree_base`.
    `branch` is the protected branch the repo is created on and the entry
    names. `other` seeds a second custody (OTHER_PRD / OTHER_OP_ID) in every
    source too: "same-repo" shares this repo_root, "other-repo" names a
    sibling directory.
    """

    def __init__(
        self,
        root: Path,
        *,
        bare: bool = False,
        empty_tree_base: bool = False,
        branch: str = "master",
        other: str | None = None,
    ) -> None:
        self.root = root
        self.autopilot_dir = root / "autopilot"
        self.autopilot_dir.mkdir()
        self.state_path = self.autopilot_dir / "state.json"
        self.marker_path = self.autopilot_dir / custody.MARKER_NAME
        self.deferred_path = (
            self.autopilot_dir / "deferred" / f"{BATCH_ID}-deferred.json"
        )
        self.repo = root / "repo"
        bare_dir = self._init_git(bare, branch)
        base = custody.EMPTY_TREE if empty_tree_base else self.shas[0]
        self.end = self.shas[2]
        # Newest first: what rev-list <base>..<end> yields and revert expects.
        self.targets = list(reversed(self.shas if empty_tree_base else self.shas[1:]))
        self.entry = {
            "prd": PRD,
            "batch": BATCH_ID,
            "op_id": OP_ID,
            "commit_range": f"{base}..{self.end}",
            "commits": len(self.targets),
            "detail": "cap-out with an unresolved CRITICAL",
            "repo_root": str(self.repo),
            "git_dir": str(bare_dir) if bare_dir else None,
            "branch": branch,
        }
        self.other: dict | None = self._other_entry(other)
        self._seed_sources([self.entry] + ([self.other] if self.other else []))

    def _init_git(self, bare: bool, branch: str) -> Path | None:
        """Create the repo, set shas / loc / git_dir; returns the bare dir."""
        bare_dir = self.root / "repo.git" if bare else None
        if bare_dir:
            self.shas = _init_bare_repo(bare_dir, self.repo)
            self.loc = ["--git-dir", str(bare_dir), "--work-tree", str(self.repo)]
        else:
            self.shas = _init_repo(self.repo, branch=branch)
            self.loc = ["-C", str(self.repo)]
        self.git_dir = bare_dir or self.repo / ".git"
        # The CLI's own git needs an identity; the global config is /dev/null.
        self.git("config", "--local", "user.email", "t@example.com")
        self.git("config", "--local", "user.name", "t")
        return bare_dir

    def _other_entry(self, other: str | None) -> dict | None:
        if not other:
            return None
        other_root = self.repo if other == "same-repo" else self.root / "other-repo"
        other_root.mkdir(exist_ok=True)
        return {
            **self.entry,
            "prd": OTHER_PRD,
            "op_id": OTHER_OP_ID,
            "repo_root": str(other_root),
            "git_dir": self.entry["git_dir"] if other == "same-repo" else None,
        }

    def _seed_sources(self, entries: list[dict]) -> None:
        """Marker, `recorded` journal rows, git-config locator, state.json."""
        custody.write_marker(self.marker_path, entries)
        for entry in entries:
            custody.append_journal(self.autopilot_dir, {"event": "recorded", **entry})
        self.git("config", "--local", custody.CONFIG_KEY, str(self.marker_path))
        # Kept as seeded: resolve may change batch.critical_on_master only.
        self.state = {
            "schema_version": 1,
            "prd": PRD,
            "phase": "build",
            "next_phase": "build",
            "cycle": 1,
            "phases_completed": [],
            "batch": {
                "id": BATCH_ID,
                "completed_prds": [],
                "parks_consecutive": 0,
                "critical_on_master": entries,
            },
        }
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    # -- seeding what a crashed earlier run leaves behind ----------------
    def seed_resolving(self, choice: str) -> None:
        """The intent row, with head_before = HEAD as it is right now."""
        custody.append_journal(
            self.autopilot_dir,
            {
                "event": "resolving",
                "op_id": OP_ID,
                "choice": choice,
                "head_before": self.head(),
            },
        )

    def seed_ledger_choice(self, choice: str) -> None:
        """A `<op_id>-resolve` record already in the batch ledger."""
        self.deferred_path.parent.mkdir(parents=True, exist_ok=True)
        item = {
            "type": "custody",
            "choice": choice,
            "prd": PRD,
            "commit_range": self.entry["commit_range"],
            "op_id": RESOLVE_ID,
        }
        self.deferred_path.write_text(
            json.dumps({"batch_id": BATCH_ID, "items": [item]}),
            encoding="utf-8",
        )

    # -- git -------------------------------------------------------------
    def git(self, *args: str) -> str:
        return _git(*self.loc, *args, cwd=self.repo)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD")

    def commit_count(self) -> int:
        return int(self.git("rev-list", "--count", "HEAD"))

    def ref(self, name: str) -> str | None:
        try:
            return self.git("rev-parse", "--verify", "--quiet", name)
        except subprocess.CalledProcessError:
            return None

    def reverted_since(self, sha: str) -> list[str]:
        """Shas named by a `This reverts commit <sha>.` line in sha..HEAD,
        one item per line, so a double revert shows up as a duplicate."""
        return _REVERTS_RE.findall(self.git("rev-list", "--format=%B", f"{sha}..HEAD"))

    def commit_file(self, name: str, content: str) -> str:
        (self.repo / name).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        return self.head()

    def files(self) -> list[str]:
        return sorted(p.name for p in self.repo.iterdir() if p.name != ".git")

    # -- custody sources ---------------------------------------------------
    def marker_op_ids(self) -> list[str]:
        return [e["op_id"] for e in custody.load_marker(self.marker_path)]

    def mirror_op_ids(self) -> list[str]:
        batch = json.loads(self.state_path.read_text(encoding="utf-8"))["batch"]
        return [e["op_id"] for e in batch.get("critical_on_master") or []]

    def resolutions(self) -> list[dict]:
        if not self.deferred_path.exists():
            return []
        items = json.loads(self.deferred_path.read_text(encoding="utf-8"))["items"]
        return [item for item in items if item.get("op_id") == RESOLVE_ID]

    def locator(self) -> str | None:
        return _locator(*self.loc)


class _ResolveCase(unittest.TestCase):
    def custody(self, **kwargs) -> _Custody:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _Custody(Path(tmp.name), **kwargs)

    def resolve(
        self,
        fx: _Custody,
        choice: str,
        prd: str = STEM,
    ) -> subprocess.CompletedProcess:
        return _run(
            "custody",
            "resolve",
            "--prd",
            prd,
            "--choice",
            choice,
            "--state",
            str(fx.state_path),
            cwd=fx.root,
        )

    def list_pending(self, fx: _Custody) -> subprocess.CompletedProcess:
        return _run("custody", "list", "--state", str(fx.state_path), cwd=fx.root)

    def assert_released(self, fx: _Custody, choice: str, *, state: bool = True) -> None:
        """OP_ID is gone from every source (marker, journal, locator, mirror)
        while any other custody survives in all of them untouched, the rest
        of state.json is byte-for-byte as seeded, and exactly one resolution
        record of the contract shape exists."""
        survivors = [fx.other] if fx.other else []
        survivor_ids = [e["op_id"] for e in survivors]
        self.assertEqual(fx.marker_op_ids(), survivor_ids)
        if not survivors:
            self.assertFalse(fx.marker_path.exists())
        self.assertEqual(
            [e["op_id"] for e in custody.pending(fx.autopilot_dir)],
            survivor_ids,
        )
        self.assertEqual(
            custody.read_journal(fx.autopilot_dir),
            [{"event": "recorded", **e} for e in survivors],
        )
        # The locator is unset only when no custody for this repo_root remains.
        if fx.other and fx.other["repo_root"] == fx.entry["repo_root"]:
            self.assertEqual(fx.locator(), str(fx.marker_path))
        else:
            self.assertIsNone(fx.locator())
        if state:
            seeded_batch = {**fx.state["batch"], "critical_on_master": survivors}
            self.assertEqual(
                json.loads(fx.state_path.read_text(encoding="utf-8")),
                {**fx.state, "batch": seeded_batch},
            )
        expected = {
            "type": "custody",
            "choice": choice,
            "prd": PRD,
            "commit_range": fx.entry["commit_range"],
            "op_id": RESOLVE_ID,
        }
        records = fx.resolutions()
        self.assertEqual(len(records), 1, records)
        self.assertEqual({k: records[0].get(k) for k in expected}, expected)

    def assert_retained(self, fx: _Custody) -> None:
        """Every custody source still names the op_id; nothing recorded."""
        self.assertEqual(fx.marker_op_ids(), [OP_ID])
        self.assertEqual(fx.locator(), str(fx.marker_path))
        self.assertEqual(fx.mirror_op_ids(), [OP_ID])
        self.assertEqual(
            [e["op_id"] for e in custody.pending(fx.autopilot_dir)],
            [OP_ID],
        )
        self.assertEqual(fx.resolutions(), [])


class RevertTests(_ResolveCase):
    def test_revert_adds_one_revert_commit_per_target_and_releases_custody(
        self,
    ) -> None:
        variants = [
            ("c0 base", {}),
            ("empty-tree base", {"empty_tree_base": True}),
            ("bare-backed repo", {"bare": True}),
            ("trunk is the protected branch", {"branch": "trunk"}),
            ("a second custody in the same repo", {"other": "same-repo"}),
            ("a second custody for another repo", {"other": "other-repo"}),
        ]
        for label, kwargs in variants:
            with self.subTest(label):
                fx = self.custody(**kwargs)
                kept = sorted(
                    f"f{i}.txt" for i in range(3) if fx.shas[i] not in fx.targets
                )

                proc = self.resolve(fx, "revert")

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("resolved (revert)", proc.stdout)
                self.assertIn(STEM, proc.stdout)
                # The revert commits land on the entry's branch, whatever it is.
                self.assertEqual(fx.branch(), fx.entry["branch"])
                self.assertEqual(fx.commit_count(), 3 + len(fx.targets))
                self.assertEqual(sorted(fx.reverted_since(fx.end)), sorted(fx.targets))
                self.assertEqual(fx.files(), kept)
                self.assertIsNone(fx.ref(CUSTODY_BRANCH))
                self.assert_released(fx, "revert")

    def test_conflicting_later_commit_exits_5_and_retains_custody(self) -> None:
        for choice in ("revert", "branch-and-revert"):
            with self.subTest(choice=choice):
                fx = self.custody()
                # Edits what the range end added, so the revert conflicts.
                later = fx.commit_file("f2.txt", "changed")

                proc = self.resolve(fx, choice)

                self.assertEqual(proc.returncode, 5)
                self.assertIn("could not revert", proc.stdout + proc.stderr)
                self.assertEqual(fx.head(), later)
                # Left for the operator: the stopped revert is still in progress.
                self.assertTrue(
                    (fx.git_dir / "REVERT_HEAD").exists()
                    or (fx.git_dir / "sequencer").is_dir(),
                )
                # The intent row was journaled before git ran, for BOTH
                # choices, keyed on the HEAD the rerun will reconcile from;
                # exactly one such row.
                intent = {
                    "event": "resolving",
                    "op_id": OP_ID,
                    "choice": choice,
                    "head_before": later,
                }
                rows = custody.read_journal(fx.autopilot_dir)
                self.assertEqual(
                    [r for r in rows if r.get("event") == "resolving"],
                    [intent],
                )
                if choice == "branch-and-revert":
                    # Intent, then the branch at the range END, then the
                    # revert: when the revert stops, the branch is already
                    # pinned, so a rerun finds it at `end` and skips it.
                    self.assertEqual(fx.ref(CUSTODY_BRANCH), fx.end)
                else:
                    self.assertIsNone(fx.ref(CUSTODY_BRANCH))
                self.assert_retained(fx)


class RerunTests(_ResolveCase):
    def test_rerun_after_revert_landed_reconciles_and_does_not_double_revert(
        self,
    ) -> None:
        fx = self.custody()
        fx.seed_resolving("revert")
        fx.git("revert", "--no-edit", *fx.targets)
        landed = fx.head()

        proc = self.resolve(fx, "revert")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(fx.head(), landed)
        self.assertEqual(sorted(fx.reverted_since(fx.end)), sorted(fx.targets))
        self.assert_released(fx, "revert")

    def test_unrelated_revert_commit_does_not_count_as_a_target(self) -> None:
        fx = self.custody()
        fx.seed_resolving("revert")
        extra = fx.commit_file("f3.txt", "f3")
        fx.git("revert", "--no-edit", extra)
        unrelated = fx.head()

        proc = self.resolve(fx, "revert")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(fx.commit_count(), 7)
        self.assertEqual(sorted(fx.reverted_since(unrelated)), sorted(fx.targets))
        self.assertEqual(fx.files(), ["f0.txt"])
        self.assert_released(fx, "revert")

    def test_partial_revert_exits_5_and_retains_custody(self) -> None:
        # (label, shas[i] reverted BEFORE the intent row, shas[i] reverted
        # after it). Reconciliation scans head_before..HEAD, so a target
        # reverted before the recorded head_before is outside the window and
        # does not count - even though it sits after the range end.
        cases = [
            ("one of the two targets reverted after head_before", [], [2]),
            ("the other target's revert sits before head_before", [2], [1]),
        ]
        for label, before, after in cases:
            with self.subTest(label):
                fx = self.custody()
                for i in before:
                    fx.git("revert", "--no-edit", fx.shas[i])
                fx.seed_resolving("revert")
                for i in after:
                    fx.git("revert", "--no-edit", fx.shas[i])
                partial = fx.head()

                proc = self.resolve(fx, "revert")

                self.assertEqual(proc.returncode, 5)
                self.assertIn("partial revert", proc.stdout + proc.stderr)
                self.assertEqual(fx.head(), partial)
                self.assert_retained(fx)

    def test_recorded_choice_wins_over_the_flag_and_only_cleans_up(self) -> None:
        cases = [("accept", "revert", 1), ("revert", "revert", 0)]
        for recorded, requested, exit_code in cases:
            with self.subTest(recorded=recorded, requested=requested):
                fx = self.custody()
                fx.seed_ledger_choice(recorded)

                proc = self.resolve(fx, requested)

                self.assertEqual(proc.returncode, exit_code, proc.stderr)
                if exit_code == 1:
                    self.assertIn(
                        f"already resolved as {recorded}",
                        proc.stdout + proc.stderr,
                    )
                self.assertEqual(fx.head(), fx.end)
                self.assertEqual(fx.commit_count(), 3)
                self.assert_released(fx, recorded)


class BranchAndRevertTests(_ResolveCase):
    def test_creates_custody_branch_at_range_end_then_reverts_on_master(self) -> None:
        # With a later commit, HEAD != range end: the branch must still pin
        # the END, and the reverts land on top of the later commit.
        variants = [("HEAD at the range end", False), ("HEAD past the range end", True)]
        for label, later_commit in variants:
            with self.subTest(label):
                fx = self.custody()
                tip = fx.commit_file("f3.txt", "f3") if later_commit else fx.end
                count = 3 + int(later_commit)

                proc = self.resolve(fx, "branch-and-revert")

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("resolved (branch-and-revert)", proc.stdout)
                self.assertEqual(fx.ref(CUSTODY_BRANCH), fx.end)
                self.assertEqual(fx.branch(), "master")
                self.assertEqual(fx.commit_count(), count + 2)
                self.assertEqual(fx.git("rev-parse", "HEAD~2"), tip)
                self.assertEqual(sorted(fx.reverted_since(tip)), sorted(fx.targets))
                self.assert_released(fx, "branch-and-revert")

                again = self.resolve(fx, "branch-and-revert")

                self.assertEqual(again.returncode, 1)
                self.assertIn("no pending custody for", again.stdout + again.stderr)
                self.assertEqual(fx.ref(CUSTODY_BRANCH), fx.end)
                self.assertEqual(fx.commit_count(), count + 2)
                self.assert_released(fx, "branch-and-revert")

    def test_rerun_with_the_custody_branch_already_present(self) -> None:
        with self.subTest("at the range end: reconciled, nothing redone"):
            fx = self.custody()
            fx.seed_resolving("branch-and-revert")
            fx.git("branch", f"custody/{STEM}", fx.end)
            fx.git("revert", "--no-edit", *fx.targets)
            landed = fx.head()

            proc = self.resolve(fx, "branch-and-revert")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(fx.ref(CUSTODY_BRANCH), fx.end)
            self.assertEqual(fx.head(), landed)
            self.assert_released(fx, "branch-and-revert")

        with self.subTest("elsewhere: refused, custody retained"):
            fx = self.custody()
            fx.git("branch", f"custody/{STEM}", fx.shas[1])

            proc = self.resolve(fx, "branch-and-revert")

            self.assertEqual(proc.returncode, 5)
            self.assertEqual(fx.ref(CUSTODY_BRANCH), fx.shas[1])
            self.assertEqual(fx.commit_count(), 3)
            self.assert_retained(fx)


class AcceptTests(_ResolveCase):
    def test_accept_leaves_git_untouched_and_releases_custody(self) -> None:
        # (label, --prd form, fixture kwargs, branch checked out beforehand).
        # Accept touches no git, so the branch check does not apply to it.
        variants = [
            ("stem", STEM, {}, None),
            ("filename", PRD, {}, None),
            ("path", str(Path("/anywhere/prds/hold") / PRD), {}, None),
            ("a second custody for another repo", STEM, {"other": "other-repo"}, None),
            ("a second custody in the same repo", STEM, {"other": "same-repo"}, None),
            ("a different checkout", STEM, {}, "other"),
        ]
        for label, prd_arg, kwargs, checkout in variants:
            with self.subTest(label):
                fx = self.custody(**kwargs)
                if checkout:
                    fx.git("checkout", "-q", "-b", checkout)

                proc = self.resolve(fx, "accept", prd=prd_arg)

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("resolved (accept)", proc.stdout)
                self.assertEqual(fx.branch(), checkout or "master")
                self.assertEqual(fx.head(), fx.end)
                self.assertEqual(fx.commit_count(), 3)
                self.assertIsNone(fx.ref(CUSTODY_BRANCH))
                self.assertEqual(fx.files(), ["f0.txt", "f1.txt", "f2.txt"])
                self.assert_released(fx, "accept")

    def test_missing_state_file_is_legal_for_list_and_resolve(self) -> None:
        fx = self.custody()
        fx.state_path.unlink()

        listed = self.list_pending(fx)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(_json_lines(listed.stdout), [fx.entry])

        proc = self.resolve(fx, "accept")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(fx.state_path.exists())
        self.assertEqual(fx.commit_count(), 3)
        self.assert_released(fx, "accept", state=False)

    def test_resolve_still_finds_the_journal_only_entry_after_the_marker_is_deleted(
        self,
    ) -> None:
        # Pending = marker UNION journal. A resolve that reads only the marker
        # answers "no pending custody" here and strands the entry forever.
        fx = self.custody()
        fx.marker_path.unlink()

        proc = self.resolve(fx, "accept")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("resolved (accept)", proc.stdout)
        self.assertEqual(fx.commit_count(), 3)
        self.assert_released(fx, "accept")


class RefusalTests(_ResolveCase):
    def test_different_checkout_exits_5_and_retains_custody(self) -> None:
        # The protected branch is the entry's, not a fixed "master".
        cases = [
            ("revert", "master"),
            ("branch-and-revert", "master"),
            ("revert", "trunk"),
        ]
        for choice, branch in cases:
            with self.subTest(choice=choice, branch=branch):
                fx = self.custody(branch=branch)
                fx.git("checkout", "-q", "-b", "other")

                proc = self.resolve(fx, choice)

                self.assertEqual(proc.returncode, 5)
                self.assertIn(f"checkout {branch} first", proc.stdout + proc.stderr)
                self.assertEqual(fx.branch(), "other")
                self.assertEqual(fx.commit_count(), 3)
                self.assertIsNone(fx.ref(CUSTODY_BRANCH))
                self.assert_retained(fx)

    def test_unknown_choice_is_a_usage_error_and_changes_nothing(self) -> None:
        fx = self.custody()

        proc = self.resolve(fx, "bogus")

        self.assertEqual(proc.returncode, 1)
        self.assertIn("usage", proc.stderr)
        self.assertIn("bogus", proc.stderr)  # the usage error names the bad choice
        self.assertEqual(fx.commit_count(), 3)
        self.assertFalse(fx.deferred_path.exists())
        self.assertEqual(
            custody.read_journal(fx.autopilot_dir),
            [{"event": "recorded", **fx.entry}],
        )
        self.assert_retained(fx)

    def test_mid_operation_repo_exits_5_and_retains_custody(self) -> None:
        for leftover in ("REVERT_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "sequencer"):
            with self.subTest(leftover=leftover):
                fx = self.custody()
                path = fx.git_dir / leftover
                if leftover == "sequencer":
                    path.mkdir()
                else:
                    path.write_text(fx.end + "\n", encoding="utf-8")

                proc = self.resolve(fx, "revert")

                self.assertEqual(proc.returncode, 5)
                self.assertIn("finish or abort it first", proc.stdout + proc.stderr)
                self.assertTrue(path.exists())
                self.assertEqual(fx.head(), fx.end)
                self.assertEqual(fx.commit_count(), 3)
                self.assert_retained(fx)

    def test_unknown_prd_exits_1_and_leaves_the_pending_entry_alone(self) -> None:
        fx = self.custody()

        proc = self.resolve(fx, "accept", prd="00099-other")

        self.assertEqual(proc.returncode, 1)
        self.assertIn("no pending custody for", proc.stdout + proc.stderr)
        self.assertIn("00099-other", proc.stdout + proc.stderr)
        self.assertEqual(fx.commit_count(), 3)
        self.assert_retained(fx)


class MirrorStaleTests(_ResolveCase):
    def test_unreadable_mirror_exits_9_with_the_custody_already_closed(self) -> None:
        # Step 5 writes the mirror LAST: the ledger record, the `resolved`
        # row, the marker release and the locator unset have all landed by
        # the time the mirror write fails, so the custody is closed (never
        # compacted) and a rerun finds nothing pending.
        fx = self.custody()
        fx.state_path.write_text("{not json", encoding="utf-8")

        proc = self.resolve(fx, "accept")

        self.assertEqual(proc.returncode, 9, proc.stderr)
        self.assertIn("mirror stale, custody closed", proc.stderr)
        self.assertEqual(fx.marker_op_ids(), [])
        self.assertFalse(fx.marker_path.exists())
        self.assertIsNone(fx.locator())
        self.assertEqual(len(fx.resolutions()), 1, fx.resolutions())
        resolved = [
            (r["op_id"], r["choice"])
            for r in custody.read_journal(fx.autopilot_dir)
            if r.get("event") == "resolved"
        ]
        self.assertEqual(resolved, [(OP_ID, "accept")])
        self.assertEqual(custody.pending(fx.autopilot_dir), [])
        self.assertEqual(fx.head(), fx.end)
        self.assertEqual(fx.commit_count(), 3)
        self.assertEqual(fx.state_path.read_text(encoding="utf-8"), "{not json")

        again = self.resolve(fx, "accept")

        self.assertEqual(again.returncode, 1)
        self.assertIn("no pending custody for", again.stdout + again.stderr)
        self.assertEqual(len(fx.resolutions()), 1, fx.resolutions())
        self.assertEqual(fx.commit_count(), 3)


class ListTests(_ResolveCase):
    def test_list_prints_each_pending_entry_as_a_json_line_and_changes_nothing(
        self,
    ) -> None:
        fx = self.custody()
        state_before = fx.state_path.read_bytes()

        proc = self.list_pending(fx)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(_json_lines(proc.stdout), [fx.entry])
        self.assertEqual(fx.state_path.read_bytes(), state_before)
        self.assert_retained(fx)

    def test_list_still_prints_the_journal_only_entry_after_the_marker_is_deleted(
        self,
    ) -> None:
        fx = self.custody()
        fx.marker_path.unlink()

        proc = self.list_pending(fx)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(_json_lines(proc.stdout), [fx.entry])
        self.assertFalse(fx.marker_path.exists())

    def test_corrupt_journal_line_exits_9_for_list_and_resolve(self) -> None:
        fx = self.custody()
        with open(fx.autopilot_dir / custody.JOURNAL_REL, "a", encoding="utf-8") as fh:
            fh.write("not json\n")
        verbs = [["list"], ["resolve", "--prd", STEM, "--choice", "accept"]]
        for verb in verbs:
            with self.subTest(verb=verb[0]):
                proc = _run(
                    "custody",
                    *verb,
                    "--state",
                    str(fx.state_path),
                    cwd=fx.root,
                )

                self.assertEqual(proc.returncode, 9)
                self.assertIn("journal", proc.stderr)
        self.assertEqual(fx.marker_op_ids(), [OP_ID])
        self.assertEqual(fx.commit_count(), 3)
        self.assertEqual(fx.resolutions(), [])


if __name__ == "__main__":
    unittest.main()
