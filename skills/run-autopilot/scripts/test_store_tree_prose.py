"""Prose pins for the store-aware dirty-tree rule (PRD 00236).

What these tests enforce:

- No skill prose teaches a clean-tree GATE off raw `git status --porcelain` /
  `--short` any more: the gate is `autopilot dirty`, which ignores the store.
  Every surviving prose mention is an inspection, a file enumeration or a
  deliberately-unrelaxed destructive precondition, and each one is named in an
  auditable allowlist below (by content, never by line number). A new
  clean-tree gate in prose fails the first test.
- The stand-down `dirty_tree` condition and the handoff procedure's
  `record-store` call sit where the design puts them.
- `STORE_GITIGNORE` and § Retention's Disposable list name the same paths.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.store_tree import STORE_GITIGNORE

_RUN_AUTOPILOT = Path(__file__).resolve().parent.parent
_SKILLS = _RUN_AUTOPILOT.parent
_SKILL = _RUN_AUTOPILOT / "SKILL.md"
_TEXT = _SKILL.read_text(encoding="utf-8")

# `--shortstat` is a diff flag, not a status gate, so it must not match.
_PORCELAIN = re.compile(r"status --porcelain|status --short(?!stat)")

# (repo-relative path, a short distinguishing substring of the exempt line).
_EXEMPT = (
    ("work/SKILL.md", "identified from `git status --porcelain` output, never guessed"),
    ("work/references/codex-implementor.md", "codex-probe-<nonce>"),
    ("work/references/codex-implementor.md", "--git-dir=<bare-git-dir>"),
    ("work/references/codex-implementor.md", "An orphaned"),
    ("work/references/rework-mode.md", "clean at claim time"),
    (
        "work/references/subagent-dispatch.md",
        "have the task's AUTHORIZED surfaces changed since dispatch?",
    ),
    ("work/references/gate-failure.md", "exits 128 with"),
    ("work/references/gate-failure.md", "--git-dir=<bare-git-dir>"),
    ("work/references/gate-failure.md", "**uncommitted:**"),
    ("work/references/gate-failure.md", "A crashed agent may have left partial"),
)


def _prose_files() -> list[Path]:
    """Every `.md` under skills/, bar the golden fixtures (frozen records)."""
    golden = _RUN_AUTOPILOT / "cli" / "golden"
    return [p for p in sorted(_SKILLS.rglob("*.md")) if golden not in p.parents]


def test_no_gate_parses_porcelain_by_hand() -> None:
    """Prose never gates on raw porcelain outside the named exemptions."""
    unexpected = []
    for path in _prose_files():
        rel = path.relative_to(_SKILLS).as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not _PORCELAIN.search(line):
                continue
            if any(rel == p and needle in line for p, needle in _EXEMPT):
                continue
            unexpected.append(f"{rel}: {line.strip()}")
    assert not unexpected, (
        "raw porcelain outside the allowlist — use `autopilot dirty` for a "
        "clean-tree gate, or add an exemption here:\n" + "\n".join(unexpected)
    )


def test_stand_down_names_autopilot_dirty() -> None:
    """The `dirty_tree` condition is measured by `autopilot dirty`."""
    start = _TEXT.index("\n## Session Loop")
    loop = _TEXT[start : _TEXT.index("\n## ", start + 1)]
    procedure = loop[loop.index("**Stand-down procedure") :]
    assert "`autopilot dirty`" in procedure
    assert "condition `dirty_tree`" in procedure
    assert not _PORCELAIN.search(procedure)


def test_handoff_procedure_records_the_store_before_the_leave_row() -> None:
    """The handoff records the store after its `leave` row, before the STOP."""
    start = _TEXT.index("### Session handoff procedure")
    procedure = _TEXT[start : _TEXT.index("\n### ", start + 1)]
    assert procedure.index("record_dispatch.py handoff") < procedure.index(
        "`autopilot record-store`"
    )


def test_store_gitignore_matches_the_disposable_list() -> None:
    """§ Retention's Disposable list and `STORE_GITIGNORE` name one set."""
    bullet = _TEXT[_TEXT.index("- **Disposable**") :]
    bullet = bullet[: bullet.index("\n")]
    # Both sides are compared without a trailing slash: STORE_GITIGNORE marks
    # directories with one (`autopilot/lanes/`), the prose does not.
    listed = {
        path.rstrip("/").removeprefix("docs/dev/project-management/")
        for path in re.findall(r"`(docs/dev/project-management/autopilot/[^`]+)`", bullet)
    }
    patterns = {p.rstrip("/") for p in STORE_GITIGNORE.split()}
    assert listed == patterns, f"drift: {listed ^ patterns}"
