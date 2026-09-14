#!/usr/bin/env python3
"""policy.py - plan-size policy for unattended runs (F5).

Exposes:
    LOOP_TASK_CEILING
        Task-count ceiling above which a PRD is too big to finish in one
        unattended run.
    plan_over_ceiling(state, ceiling=LOOP_TASK_CEILING) -> (over, count)
        PURE. `count` is always len(state["tasks"]) computed here, never a
        caller-supplied number: a model that miscounts its own plan is the
        exact failure this gate exists to catch. A missing or non-list
        "tasks" counts as 0 - nothing planned yet is not oversized.
    EXPANSION_RATIO_MAX, EXPANSION_MIN_TASKS, MODULE_DRIFT_MAX,
    PLAN_EXPANSION_OVERRIDE_KEY
        Thresholds and the frontmatter key of the plan-expansion verdict.
    Verdict
        Frozen result of plan_expansion: the decision, the numbers behind
        it, and the Markdown split note.
    prd_task_lines(prd_text) -> int
        Top-level `- [ ]` / `- [x]` checkbox lines in the PRD body.
    prd_modules(prd_text) -> (leaf_dirs, listed_files) | None
        Leaf directories and listed files from the PRD's fenced
        `### Repository Structure` tree; None when there is no such tree.
    plan_expansion(state, prd_text, ceiling=LOOP_TASK_CEILING) -> Verdict
        PURE. Fires task_count, expansion and module_drift in that order;
        `plan_expansion: allow` in the PRD frontmatter skips every rule
        while the note still reports what would have fired.

Origin: the 2026-07-28 loop evaluation, fix F5. PRD 00077 planned to 28
tasks, then burned 15 sessions / 21.5h / $351 across three wall-clock cap
kills without converging, and halted the batch for four days. PRD 00071
(22 tasks) did land, so the ceiling is deliberately conservative rather
than fitted to those two points - it stalls for a human, it never refuses
to plan.
"""

from __future__ import annotations

import dataclasses
import posixpath
import re

from . import frontmatter

LOOP_TASK_CEILING = 15


def plan_over_ceiling(
    state: dict, ceiling: int = LOOP_TASK_CEILING
) -> tuple[bool, int]:
    """Return (over_ceiling, task_count) for `state`'s task snapshot."""
    tasks = state.get("tasks")
    count = len(tasks) if isinstance(tasks, list) else 0
    return count > ceiling, count


EXPANSION_RATIO_MAX = 3.0
EXPANSION_MIN_TASKS = 8
MODULE_DRIFT_MAX = 1
PLAN_EXPANSION_OVERRIDE_KEY = "plan_expansion"

_TASK_LINE = re.compile(r"^- \[[ x]\]", re.MULTILINE)
_TREE_HEADING = "### Repository Structure"
_TREE_COLUMNS = ("├── ", "└── ", "│   ", "    ")

Modules = tuple[tuple[str, ...], tuple[str, ...]]


@dataclasses.dataclass(frozen=True)
class Verdict:
    """The plan-expansion decision, its numbers, and the split note."""

    stall: bool
    reasons: tuple[str, ...]
    planned: int
    prd_tasks: int
    expansion: float | None
    drift: tuple[str, ...]
    unfiled: int
    override: bool
    note: str


def prd_task_lines(prd_text: str) -> int:
    """Count the PRD's top-level `- [ ]` / `- [x]` checkbox lines."""
    return len(_TASK_LINE.findall(prd_text))


def _tree_block(prd_text: str) -> list[str] | None:
    """Lines inside the fence under `### Repository Structure`, or None
    when the heading is missing or no fence opens before the next heading."""
    lines = prd_text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(_TREE_HEADING)), None
    )
    if start is None:
        return None
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("#"):
            return None
        if lines[i].startswith("```"):
            body = lines[i + 1 :]
            end = next(
                (j for j, line in enumerate(body) if line.startswith("```")), len(body)
            )
            return body[:end]
    return None


def _tree_entries(block: list[str]) -> tuple[set[str], set[str]]:
    """(recorded dirs, listed files) from the ASCII tree, one entry per line."""
    dirs: set[str] = set()
    files: set[str] = set()
    stack: list[tuple[int, str]] = []
    for raw in block:
        name = raw.split(" #", 1)[0].rstrip()
        depth = 0
        while name[:4] in _TREE_COLUMNS:
            depth += 1
            name = name[4:]
        if not name:
            continue
        while stack and stack[-1][0] >= depth:
            stack.pop()
        path = posixpath.join(stack[-1][1], name) if stack else name
        if not path.endswith("/"):
            files.add(path)
            continue
        path = path.rstrip("/")
        stack.append((depth, path))
        while path and path != ".":
            dirs.add(path)
            path = posixpath.dirname(path)
    return dirs, files


def prd_modules(prd_text: str) -> Modules | None:
    """(sorted leaf dirs, sorted listed files) from the PRD's Repository
    Structure tree, or None when the PRD carries no such fenced tree."""
    block = _tree_block(prd_text)
    if block is None:
        return None
    dirs, files = _tree_entries(block)
    leaves = [d for d in dirs if not any(o.startswith(d + "/") for o in dirs)]
    return tuple(sorted(leaves)), tuple(sorted(files))


def _file_module(path: str, modules: Modules) -> tuple[str, bool]:
    """(module, covered) for one task file against the PRD tree."""
    leaf_dirs, listed = modules
    for leaf in leaf_dirs:
        if path.startswith(leaf + "/"):
            return leaf, True
    return posixpath.dirname(path) or ".", path in listed


def _group_tasks(
    tasks: list, modules: Modules
) -> tuple[dict[str, list[str]], list[str], set[str]]:
    """Note lines per module in task order, the unfiled task lines, and the
    set of modules holding at least one uncovered file."""
    by_module: dict[str, list[str]] = {}
    unfiled: list[str] = []
    uncovered: set[str] = set()
    for index, task in enumerate(tasks):
        label = f"{task.get('id', index)} {task.get('name', '')}"
        files = task.get("files")
        if not isinstance(files, list) or not files:
            unfiled.append(f"- {label}")
            continue
        per_module: dict[str, list[str]] = {}
        for path in files:
            if not isinstance(path, str):
                continue
            module, covered = _file_module(path, modules)
            per_module.setdefault(module, []).append(path)
            if not covered:
                uncovered.add(module)
        for module, paths in per_module.items():
            by_module.setdefault(module, []).append(f"- {label}: {', '.join(paths)}")
    return by_module, unfiled, uncovered


def _fired_rules(
    planned: int, ceiling: int, expansion: float | None, drift: tuple[str, ...] | None
) -> tuple[str, ...]:
    """The rules that fire, in the fixed task_count, expansion, module_drift
    order; `drift` is None when the PRD has no tree to drift from."""
    checks = (
        ("task_count", planned > ceiling),
        (
            "expansion",
            expansion is not None
            and expansion > EXPANSION_RATIO_MAX
            and planned > EXPANSION_MIN_TASKS,
        ),
        ("module_drift", drift is not None and len(drift) > MODULE_DRIFT_MAX),
    )
    return tuple(name for name, hit in checks if hit)


def _render_note(
    header: list[str],
    by_module: dict[str, list[str]],
    unfiled: list[str],
    uncovered: set[str],
) -> str:
    """The Markdown split note: header lines, one section per module
    (UNLISTED first, then listed, each sorted), then the unfiled tasks."""
    unlisted = sorted(m for m in by_module if m in uncovered)
    listed = sorted(m for m in by_module if m not in uncovered)
    sections = [(f"{m} (UNLISTED)", by_module[m]) for m in unlisted]
    sections += [(f"{m} (listed)", by_module[m]) for m in listed]
    if unfiled:
        sections.append(("(no files declared)", unfiled))
    parts = ["\n".join(header)]
    parts += [f"## {heading}\n\n" + "\n".join(lines) for heading, lines in sections]
    return "\n\n".join(parts) + "\n"


def plan_expansion(
    state: dict, prd_text: str, ceiling: int = LOOP_TASK_CEILING
) -> Verdict:
    """Decide whether the plan in `state` outgrew the PRD it came from."""
    _over, planned = plan_over_ceiling(state, ceiling)
    prd_tasks = prd_task_lines(prd_text)
    expansion = planned / prd_tasks if prd_tasks else None
    modules = prd_modules(prd_text)
    tasks = state.get("tasks")
    by_module, unfiled, uncovered = _group_tasks(
        tasks if isinstance(tasks, list) else [], modules or ((), ())
    )
    drift = () if modules is None else tuple(sorted(uncovered))
    fired = _fired_rules(planned, ceiling, expansion, None if modules is None else drift)
    override = frontmatter.parse(prd_text)[0].get("plan_expansion_override") is True
    reasons = () if override else fired
    ratio = "n/a" if expansion is None else f"{expansion:.2f}"
    header = [
        f"# Split note: {state.get('prd', '')}",
        (
            f"planned={planned} prd_tasks={prd_tasks} expansion={ratio} "
            f"reasons={', '.join(reasons) or 'none'}"
        ),
    ]
    if modules is None:
        header.append("drift: skipped (no Repository Structure)")
    if override:
        header.append(
            f"override: {PLAN_EXPANSION_OVERRIDE_KEY}: allow "
            f"(rules skipped: {', '.join(fired) or 'none'})"
        )
    return Verdict(
        stall=bool(reasons),
        reasons=reasons,
        planned=planned,
        prd_tasks=prd_tasks,
        expansion=expansion,
        drift=drift,
        unfiled=len(unfiled),
        override=override,
        note=_render_note(header, by_module, unfiled, uncovered),
    )
