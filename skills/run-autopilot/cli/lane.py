#!/usr/bin/env python3
"""lane.py - which effort lane a PRD takes: solo, fast-track or full.

PURE: reads the PRD's TEXT and the flat frontmatter pairs the caller already
parsed (`frontmatter.declared`), returns a Verdict. No disk, no state, no git.
The two path predicates it needs (`is_test_path`, `is_packaging_path`) are
loaded by path from the skills that own them, never copied, so every skill
judges a path alike.

    named_paths(text)              -> the repo-relative paths the PRD names
    is_hook_path(path)             -> hooks/ segment, hooks.json, *_hook.py
    is_production_path(path)       -> not test, not doc, not packaging
    securityish(text)              -> the review-fanout security trigger
    security_triggered(diff, files)-> the diff-level trigger, ported
    plan_cards(text)               -> the fast-track card split, or []
    classify(text, declared)       -> Verdict(lane, reason, paths, ...)
    effective(lane, lanes_env)     -> the lane that actually runs

Seven ordered rules, first match wins, and `reason` names the rule that
paid for the lane (the `classify_tier._tier_from_shape` shape). Every rule
fails toward `full`: an unparsed PRD, a hook path, a security-ish path and
an absent `design: skip` all take the expensive lane. `default_model` never
decides the lane.
"""

from __future__ import annotations

import importlib.util
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parents[2]

LANES = ("solo", "fast-track", "full")

# The lanes whose runbook has shipped. A classified lane outside this set
# still runs full (`effective`), so the classifier can be measured before a
# lane goes live. `solo` shipped with PRD 00205 (`references/lane-solo.md`).
RELEASED_LANES = frozenset({"full", "solo"})

# The fast-track card limits (`skills/fast-track/scripts/card.py`).
CARD_MAX_FILES = 12
CARD_MAX_GOAL_LINES = 40

# The `review-fanout` workflow's SECURITY_RE, ported verbatim: matched against
# camel-split, lowercased text, so `authToken` hits both terms while
# `execute` and `hashmap` hit none.
SECURITY_RE = re.compile(
    r"(?<![a-z0-9])(?:(?:exec|eval|auth|token|password|secret|sql|crypto|hash"
    r"|credential|session|cookie|csrf|xss|jwt|sanitize|injection|privilege)s?"
    r"(?![a-z0-9])|authenticat|authoriz|permission|login|forbidden|acl)",
)
_CAMEL_SPLIT = re.compile(r"([a-z0-9])([A-Z])")

_DOC_SUFFIXES = (".md", ".txt", ".rst")
_HOOK_BASENAMES = ("hooks.json",)

_TREE_HEADING = "### Repository Structure"
_TREE_COLUMNS = ("├── ", "└── ", "│   ", "    ")
_LOCATION_LINE = re.compile(r"^\s*-\s+\*\*Location\*\*:")
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")
_LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")
_PATH_SHAPE = re.compile(r"^[\w./*-]+$")

_TASK_ITEM = re.compile(r"^- \[[ x]\] ")
_TASK_CONTINUATION = re.compile(r"^ {2,}\S")
_PHASE_HEADING = re.compile(r"^### Phase \d+:")
_PHASE_PARENTS = ("## Tasks", "## Implementation Phases")
_PROBLEM_HEADINGS = ("### Problem Statement", "## Problem")


def _load_by_path(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, _SKILLS_DIR / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


is_test_path = _load_by_path(
    "work_routing", "work/scripts/work_routing.py"
).is_test_path
is_packaging_path = _load_by_path(
    "classify_tier",
    "plan-tasks/scripts/classify_tier.py",
).is_packaging_path


# ── named paths ──────────────────────────────────────────────────────────────


def _candidate(raw: str) -> str | None:
    """`raw` as a named path, or None when it does not look like one: a
    trailing `:N` / `:N-M` citation is stripped first, then the text must be
    path-shaped and hold a `.` or a `/` (so `render_brief()` and
    `_add_check_plan` are symbols, `CHANGELOG.md` and `dev/bin/release-checks`
    are paths)."""
    text = _LINE_SUFFIX.sub("", raw.strip())
    if text.endswith("/"):
        return None  # a directory, never a named path
    if not _PATH_SHAPE.fullmatch(text) or not ("." in text or "/" in text):
        return None
    return text


def _tree_block(lines: list[str]) -> tuple[int, list[str]] | None:
    """(first line index, fence body) of the first fenced block after the
    `### Repository Structure` heading, or None when there is none."""
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
            return i + 1, body[:end]
    return None


def _tree_siblings(name: str) -> list[str]:
    """One tree line's entries: a line holding `, ` splits into siblings, and
    a sibling without a `/` takes the directory of the item before it."""
    if ", " not in name:
        return [name]
    out: list[str] = []
    for part in (p.strip() for p in name.split(", ")):
        if not part:
            continue
        if "/" not in part and out:
            part = posixpath.join(posixpath.dirname(out[-1]), part)
        out.append(part)
    return out


def _tree_paths(block: list[str]) -> list[str]:
    """Full paths of the file entries in the ASCII tree, in line order.
    A glyph line's depth is its count of 4-character columns and it belongs
    to the nearest preceding directory at a lesser depth; a name ending in
    `/` is a directory and is never a named path."""
    paths: list[str] = []
    stack: list[tuple[int, str]] = []
    for raw in block:
        name = raw.split(" #", 1)[0].rstrip()
        depth = 0
        while name[:4] in _TREE_COLUMNS:
            depth += 1
            name = name[4:]
        if not name.strip():
            continue
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1] if stack else ""
        for entry in _tree_siblings(name.strip()):
            path = posixpath.join(parent, entry) if parent else entry
            if path.endswith("/"):
                stack.append((depth, path.rstrip("/")))
            else:
                paths.append(path)
    return paths


def named_paths(text: str) -> tuple[str, ...]:
    """The repo-relative paths the PRD names, first-appearance order, deduplicated:
    the Repository Structure tree's file entries and every backticked span on
    a `- **Location**:` line, each passed through `_candidate`."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    tree = _tree_block(lines)
    if tree is not None:
        first, block = tree
        found += [(first, path) for path in _tree_paths(block)]
    for index, line in enumerate(lines):
        if _LOCATION_LINE.match(line):
            found += [(index, span) for span in _BACKTICK_SPAN.findall(line)]
    out: list[str] = []
    for _index, raw in sorted(found, key=lambda pair: pair[0]):
        path = _candidate(raw)
        if path is not None and path not in out:
            out.append(path)
    return tuple(out)


# ── path kinds ───────────────────────────────────────────────────────────────


def is_hook_path(path: str) -> bool:
    """A hook: any `hooks` directory segment, basename `hooks.json`, or a
    basename matching `*_hook.py`."""
    segments = path.split("/")
    if "hooks" in segments[:-1]:
        return True
    basename = segments[-1]
    return basename in _HOOK_BASENAMES or basename.endswith("_hook.py")


def is_production_path(path: str) -> bool:
    """Not a test path, not a doc (`.md`, `.txt`, `.rst`), not packaging."""
    if is_test_path(path) or is_packaging_path(path):
        return False
    return not path.lower().endswith(_DOC_SUFFIXES)


def securityish(text: str) -> bool:
    """Split camelCase so `authToken` yields both words, lowercase, search."""
    return SECURITY_RE.search(_CAMEL_SPLIT.sub(r"\1 \2", str(text)).lower()) is not None


def _is_dash_header(line: str | None) -> bool:
    return line is not None and re.match(r"^---(?:\s|$)", line) is not None


def _is_plus_header(line: str | None) -> bool:
    return line is not None and re.match(r"^\+\+\+(?:\s|$)", line) is not None


def security_triggered(diff: str, changed_files: list[str] | tuple[str, ...]) -> bool:
    """The `review-fanout` `securityTriggered` port: a security-ish changed
    path fires; a `---`/`+++` file header is skipped only as an adjacent
    pair; every other added or removed line is tested with `securityish`
    (a guard disappearing is as strong a signal as one appearing)."""
    for path in changed_files or ():
        if securityish(path):
            return True
    lines = str(diff or "").split("\n")
    for index, line in enumerate(lines):
        before = lines[index - 1] if index > 0 else None
        after = lines[index + 1] if index + 1 < len(lines) else None
        is_header = (_is_dash_header(line) and _is_plus_header(after)) or (
            _is_plus_header(line) and _is_dash_header(before)
        )
        if is_header:
            continue
        if (line.startswith("+") or line.startswith("-")) and securityish(line):
            return True
    return False


# ── card plan ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CardPlan:
    """One fast-track card's plan: the phase heading it came from (None for
    a whole-PRD card), its writable files, its `## Goal` lines and the task
    items those lines end with."""

    phase: str | None
    files: tuple[str, ...]
    goal_lines: tuple[str, ...]
    task_items: tuple[str, ...]


def _task_items(lines: list[str]) -> list[str]:
    """Each `- [ ]` line joined with its indented continuation lines into
    ONE line (single spaces), before any count."""
    items: list[str] = []
    open_item = False
    for line in lines:
        if _TASK_ITEM.match(line):
            items.append(" ".join(line.split()))
            open_item = True
        elif open_item and _TASK_CONTINUATION.match(line):
            items[-1] = f"{items[-1]} {' '.join(line.split())}"
        else:
            open_item = False
    return items


def _section(lines: list[str], headings: tuple[str, ...]) -> list[str]:
    """The body under the first of `headings` found, up to the next heading."""
    for index, line in enumerate(lines):
        if line.strip() in headings:
            body: list[str] = []
            for later in lines[index + 1 :]:
                if later.startswith("#"):
                    break
                body.append(later.rstrip())
            return body
    return []


def _phases(lines: list[str]) -> list[tuple[str, list[str]]]:
    """(heading, task items) per `### Phase N:` heading under `## Tasks` or
    `## Implementation Phases`, holding the lines up to the next `### ` or
    `## ` heading. A `## Dependency Graph` layer heading ends in `(Phase N)`
    and never matches."""
    phases: list[tuple[str, list[str]]] = []
    under_parent = False
    current: list[str] | None = None
    for line in lines:
        if line.startswith("## "):
            under_parent = line.strip() in _PHASE_PARENTS
            current = None
            continue
        if line.startswith("### "):
            current = None
            if under_parent and _PHASE_HEADING.match(line):
                current = []
                phases.append((line[4:].strip(), current))
            continue
        if current is not None:
            current.append(line)
    return [(heading, _task_items(body)) for heading, body in phases]


def _problem_lines(lines: list[str]) -> list[str]:
    text = "\n".join(_section(lines, _PROBLEM_HEADINGS)).strip()
    return text.splitlines() if text else []


def _fits(files: tuple[str, ...], goal: tuple[str, ...]) -> bool:
    return len(files) <= CARD_MAX_FILES and len(goal) <= CARD_MAX_GOAL_LINES


def _phase_files(
    paths: tuple[str, ...],
    own_text: str,
    all_text: str,
) -> tuple[str, ...]:
    """The named paths whose basename occurs in this phase's task text, plus
    every named path whose basename no phase's task text names (a file no
    task names must still be writable, so it goes to every card)."""
    out = []
    for path in paths:
        basename = posixpath.basename(path)
        if basename in own_text or basename not in all_text:
            out.append(path)
    return tuple(out)


def plan_cards(text: str) -> list[CardPlan]:
    """One whole-PRD plan when every named path fits 12 and the goal fits
    40 lines; else one plan per phase when there are exactly two phases and
    both fit; else `[]`. A glob among the named paths makes the plan empty:
    fast-track's file allowlist is literal."""
    paths = named_paths(text)
    if not paths or any("*" in path for path in paths):
        return []
    lines = text.splitlines()
    problem = tuple(_problem_lines(lines))
    items = tuple(_task_items(lines))
    whole_goal = problem + items
    if _fits(paths, whole_goal):
        return [CardPlan(None, paths, whole_goal, items)]
    phases = _phases(lines)
    if len(phases) != 2:
        return []
    all_text = " ".join(" ".join(body) for _heading, body in phases)
    plans = []
    for heading, body in phases:
        files = _phase_files(paths, " ".join(body), all_text)
        goal = problem + tuple(body)
        if not _fits(files, goal):
            return []
        plans.append(CardPlan(heading, files, goal, tuple(body)))
    return plans


# ── classify ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Verdict:
    """The lane, the first rule that matched, and the evidence it read."""

    lane: str
    reason: str
    paths: tuple[str, ...]
    prod_paths: tuple[str, ...]
    cards: int


def classify(text: str, declared: dict[str, str]) -> Verdict:
    """The seven ordered rules; `declared` is `frontmatter.declared(text)`.
    An invalid `lane:` value is treated as absent here (the verb warns)."""
    paths = named_paths(text)
    prod = tuple(path for path in paths if is_production_path(path))
    cards = len(plan_cards(text))

    def verdict(lane: str, reason: str) -> Verdict:
        return Verdict(lane, reason, paths, prod, cards)

    override = declared.get("lane")
    if override in LANES:
        return verdict(override, "override")
    if any(is_hook_path(path) for path in paths):
        return verdict("full", "hook")
    if any(securityish(path) for path in paths):
        return verdict("full", "security_path")
    if not paths:
        return verdict("full", "unparsed")
    if declared.get("design") != "skip":
        return verdict("full", "design")
    if not prod:
        return verdict("solo", "no_production_code")
    if cards:
        return verdict("fast-track", "card_sized")
    return verdict("full", "uncardable")


def effective(lane: str, lanes_env: str | None) -> str:
    """The lane that runs: `full` under `_AUTOPILOT_LANES=off` or for a lane
    whose runbook has not shipped, else the classified lane."""
    if lanes_env == "off" or lane not in RELEASED_LANES:
        return "full"
    return lane
